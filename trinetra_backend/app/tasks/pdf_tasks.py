import json
import structlog
from datetime import datetime
from celery import shared_task
from sqlalchemy.orm import Session
from sqlalchemy import create_engine
from app.core.config import settings
from app.core.celery_app import celery_app
from app.models.models import ProcessingJob, AgentOutput, EmailRecord, JobStatus, EmailStatus
from app.services.pdf_service import pdf_service
from app.agents.crew_agents import run_agent_pipeline
from app.services.email_service import email_service

logger = structlog.get_logger()

engine = create_engine(settings.SYNC_DATABASE_URL)

def get_sync_db():
    return Session(engine)

@celery_app.task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    name="app.tasks.pdf_tasks.process_pdf_task"
)
def process_pdf_task(self, job_id: str, file_path: str, recipient_email: str):
    db = get_sync_db()
    try:
        job = db.query(ProcessingJob).filter(ProcessingJob.id == job_id).first()
        if not job:
            logger.error("job_not_found", job_id=job_id)
            return

        job.status = JobStatus.PROCESSING
        job.celery_task_id = self.request.id
        job.updated_at = datetime.utcnow()
        db.commit()
        logger.info("job_processing_started", job_id=job_id)

        extracted_data = pdf_service.extract_text(file_path)
        logger.info("pdf_extracted", job_id=job_id)

        agent_result = run_agent_pipeline(extracted_data, recipient_email)
        logger.info("agents_completed", job_id=job_id)

        agent_output = AgentOutput(
            job_id=job_id,
            extracted_text=extracted_data.get("full_text", "")[:10000],
            structured_data=json.dumps(agent_result.get("analysis", "")),
            email_subject=agent_result.get("email_subject", "Document Summary"),
            email_body=agent_result.get("email_body", ""),
        )
        db.add(agent_output)

        email_record = EmailRecord(
            job_id=job_id,
            recipient_email=recipient_email,
            subject=agent_result.get("email_subject", "Document Summary"),
            status=EmailStatus.QUEUED,
        )
        db.add(email_record)
        db.commit()

        send_email_task.delay(
            str(email_record.id),
            recipient_email,
            agent_result.get("email_subject", "Document Summary"),
            agent_result.get("email_body", ""),
        )

        job.status = JobStatus.COMPLETED
        job.updated_at = datetime.utcnow()
        db.commit()
        logger.info("job_completed", job_id=job_id)

    except Exception as e:
        logger.error("job_failed", job_id=job_id, error=str(e))
        try:
            job = db.query(ProcessingJob).filter(ProcessingJob.id == job_id).first()
            if job:
                job.status = JobStatus.FAILED
                job.error_message = str(e)
                job.updated_at = datetime.utcnow()
                db.commit()
        except Exception:
            pass
        raise self.retry(exc=e, countdown=2 ** self.request.retries * 30)
    finally:
        db.close()


@celery_app.task(
    bind=True,
    max_retries=3,
    default_retry_delay=30,
    name="app.tasks.pdf_tasks.send_email_task"
)
def send_email_task(self, email_record_id: str, recipient: str, subject: str, body: str):
    db = get_sync_db()
    try:
        result = email_service.send_email(recipient, subject, body)

        record = db.query(EmailRecord).filter(EmailRecord.id == email_record_id).first()
        if record:
            if result.get("success"):
                record.status = EmailStatus.SENT
                record.sendgrid_message_id = result.get("message_id", "")
                record.sent_at = datetime.utcnow()
            else:
                record.status = EmailStatus.FAILED
                record.error_message = result.get("error", "")
            db.commit()

        logger.info("email_task_completed", email_record_id=email_record_id, success=result.get("success"))

    except Exception as e:
        logger.error("email_task_failed", email_record_id=email_record_id, error=str(e))
        raise self.retry(exc=e, countdown=2 ** self.request.retries * 15)
    finally:
        db.close()
