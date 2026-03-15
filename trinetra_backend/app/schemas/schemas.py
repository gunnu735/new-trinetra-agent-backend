from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime
from uuid import UUID
from app.models.models import JobStatus, EmailStatus

class UserCreate(BaseModel):
    email: str
    name: str

class UserResponse(BaseModel):
    id: UUID
    email: str
    name: str
    created_at: datetime
    class Config:
        from_attributes = True

class DocumentResponse(BaseModel):
    id: UUID
    filename: str
    file_size: int
    created_at: datetime
    class Config:
        from_attributes = True

class JobResponse(BaseModel):
    id: UUID
    status: JobStatus
    celery_task_id: Optional[str] = None
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    class Config:
        from_attributes = True

class UploadResponse(BaseModel):
    message: str
    job_id: UUID
    document_id: UUID

class AgentOutputResponse(BaseModel):
    id: UUID
    extracted_text: Optional[str] = None
    structured_data: Optional[str] = None
    email_subject: Optional[str] = None
    email_body: Optional[str] = None
    created_at: datetime
    class Config:
        from_attributes = True

class EmailRecordResponse(BaseModel):
    id: UUID
    recipient_email: str
    subject: Optional[str] = None
    status: EmailStatus
    sendgrid_message_id: Optional[str] = None
    sent_at: Optional[datetime] = None
    created_at: datetime
    class Config:
        from_attributes = True

class JobDetailResponse(BaseModel):
    job: JobResponse
    agent_output: Optional[AgentOutputResponse] = None
    email_record: Optional[EmailRecordResponse] = None
