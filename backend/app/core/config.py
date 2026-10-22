from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, field_validator
from typing import List, Union, Any
import os


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # Environment
    ENVIRONMENT: str = "development"
    DEBUG: bool = True

    # Application
    PROJECT_NAME: str = "Multi-Tenant RAG API"
    API_V1_STR: str = "/api/v1"
    BACKEND_CORS_ORIGINS: Union[List[str], str] = ["*"]

    @field_validator("BACKEND_CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Any) -> List[str]:
        if isinstance(v, str):
            v = v.strip()
            if v.startswith("[") and v.endswith("]"):
                import json
                try:
                    return json.loads(v)
                except Exception:
                    pass
            return [i.strip() for i in v.split(",") if i.strip()]
        elif isinstance(v, (list, tuple)):
            return list(v)
        return ["*"]

    # Security & Auth
    SECRET_KEY: str = Field(
        default="change-me-super-secret-key-production-ready",
        description="JWT secret key",
    )
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # PostgreSQL Database
    DATABASE_URL: str = Field(
        default="postgresql+asyncpg://postgres:postgres@localhost:5432/rag_db",
        description="Async SQLAlchemy database URL (PostgreSQL with pgvector)",
    )

    # Redis & Celery
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/0"

    # Storage
    UPLOAD_DIR: str = "./uploads"

    # AI / LLM Configuration
    GOOGLE_API_KEY: str = ""
    OPENAI_API_KEY: str = ""
    GROQ_API_KEY: str = ""
    GROQ_MODEL: str = "llama-3.3-70b-versatile"
    HUGGINGFACE_API_KEY: str = ""
    HUGGINGFACE_EMBEDDING_MODEL: str = "BAAI/bge-base-en-v1.5"
    EMBEDDING_MODEL_PROVIDER: str = "google"
    LLM_MODEL_PROVIDER: str = "google"
    EMBEDDING_DIMENSION: int = 768


settings = Settings()
