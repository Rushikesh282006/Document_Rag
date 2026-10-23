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

    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def assemble_database_url(cls, v: Any) -> str:
        if isinstance(v, str):
            from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
            parsed = urlparse(v)
            scheme = parsed.scheme
            if scheme in ("postgresql", "postgres", "postgresql+psycopg2"):
                scheme = "postgresql+asyncpg"

            params = parse_qs(parsed.query)
            new_params = {}

            # asyncpg expects 'ssl=require' instead of libpq's 'sslmode=require'
            if "ssl" in params or "sslmode" in params:
                ssl_val = params.get("ssl", params.get("sslmode", ["require"]))[0]
                if ssl_val not in ("disable", "false", "0"):
                    new_params["ssl"] = "require"

            # Whitelist valid asyncpg connection parameters and discard libpq-only parameters
            # (such as channel_binding, gssencmode, sslrootcert, etc.)
            asyncpg_valid_params = {"timeout", "command_timeout", "statement_cache_size", "server_settings"}
            for k, val in params.items():
                if k in asyncpg_valid_params:
                    new_params[k] = val[0]

            new_query = urlencode(new_params)
            return urlunparse(parsed._replace(scheme=scheme, query=new_query))
        return str(v)

    # Redis & Celery
    REDIS_URL: Union[str, None] = None
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/0"

    @field_validator("CELERY_BROKER_URL", mode="before")
    @classmethod
    def assemble_celery_broker(cls, v: Any) -> str:
        redis_env = os.environ.get("REDIS_URL") or os.environ.get("REDIS_TLS_URL")
        if redis_env:
            return redis_env
        return str(v) if v else "redis://localhost:6379/0"

    @field_validator("CELERY_RESULT_BACKEND", mode="before")
    @classmethod
    def assemble_celery_backend(cls, v: Any) -> str:
        redis_env = os.environ.get("REDIS_URL") or os.environ.get("REDIS_TLS_URL")
        if redis_env:
            return redis_env
        return str(v) if v else "redis://localhost:6379/0"

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
