import uuid
import structlog
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.database import get_db
from app.models.models import User, Document, ProcessingJob, AgentOutput, EmailRecord, JobStatus
from app.schemas.schemas import UploadResponse, JobResponse, JobDetailResponse, UserCreate, UserResponse
from app.services.pdf_service import pdf_service
from app.tasks.pdf_tasks import process_pdf_task

router = APIRouter()
logger = structlog.get_logger()

@router.post("/users", response_model=UserResponse)
async def create_user(user_data: UserCreate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == user_data.email))
    existing = result.scalar_one_or_none()
    if existing:
        return existing
    user = User(email=user_data.email, name=user_data.name)
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user

@router.post("/upload", response_model=UploadResponse)
async def upload_pdf(
    file: UploadFile = File(...),
    user_id: str = Form(...),
    recipient_email: str = Form(...),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(User).where(User.id == uuid.UUID(user_id)))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    file_info = await pdf_service.validate_and_save(file)

    document = Document(
        user_id=uuid.UUID(user_id),
        filename=file.filename,
        file_path=file_info["file_path"],
        file_size=file_info["file_size"],
    )
    db.add(document)
    await db.flush()

    job = ProcessingJob(
        document_id=document.id,
        status=JobStatus.PENDING,
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)

    process_pdf_task.delay(
        str(job.id),
        file_info["file_path"],
        recipient_email,
    )

    logger.info("upload_queued", job_id=str(job.id), document_id=str(document.id))
    return UploadResponse(
        message="PDF uploaded and processing started",
        job_id=job.id,
        document_id=document.id,
    )

@router.get("/jobs/{job_id}", response_model=JobDetailResponse)
async def get_job_status(job_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(ProcessingJob).where(ProcessingJob.id == uuid.UUID(job_id)))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    agent_result = await db.execute(select(AgentOutput).where(AgentOutput.job_id == uuid.UUID(job_id)))
    agent_output = agent_result.scalar_one_or_none()

    email_result = await db.execute(select(EmailRecord).where(EmailRecord.job_id == uuid.UUID(job_id)))
    email_record = email_result.scalar_one_or_none()

    return JobDetailResponse(job=job, agent_output=agent_output, email_record=email_record)

@router.get("/jobs", response_model=list[JobResponse])
async def list_jobs(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(ProcessingJob).order_by(ProcessingJob.created_at.desc()).limit(50))
    jobs = result.scalars().all()
    return jobs
