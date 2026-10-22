from collections.abc import AsyncGenerator
# pyrefly: ignore [missing-import]
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from app.core.config import settings

from sqlalchemy.pool import NullPool

# Web application pooled engine
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)

# Dedicated engine for Celery background workers (NullPool prevents event-loop binding conflicts)
worker_engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    poolclass=NullPool,
)

AsyncWorkerSessionLocal = async_sessionmaker(
    bind=worker_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)



async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency that provides an async database session per request."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
