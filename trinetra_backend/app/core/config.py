from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    APP_NAME: str = "Trinetra Backend"
    DEBUG: bool = True
    SECRET_KEY: str = "secret"

    DATABASE_URL: str
    SYNC_DATABASE_URL: str

    REDIS_URL: str = "redis://localhost:6379/0"

    GROQ_API_KEY: str
    SENDGRID_API_KEY: str
    EMAIL_FROM: str
    EMAIL_FROM_NAME: str = "Trinetra Labs"

    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/0"

    MAX_FILE_SIZE_MB: int = 50
    UPLOAD_DIR: str = "uploads"

    class Config:
        env_file = ".env"
        extra = "allow"

settings = Settings()
