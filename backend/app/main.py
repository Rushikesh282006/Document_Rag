from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
import logging
from pathlib import Path

from fastapi import FastAPI, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from slowapi.errors import RateLimitExceeded

from app.api.router import api_router
from app.core.config import settings
from app.core.rate_limit import limiter, rate_limit_exceeded_handler

# Setup standard logging
logging.basicConfig(
    level=logging.INFO if not settings.DEBUG else logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan context manager for startup and shutdown routines."""
    logger.info("Initializing application resources...")
    
    # Ensure upload directory exists
    upload_path = Path(settings.UPLOAD_DIR)
    upload_path.mkdir(parents=True, exist_ok=True)
    
    logger.info(f"Upload directory verified at: {upload_path.resolve()}")
    logger.info(f"{settings.PROJECT_NAME} startup complete.")
    
    yield
    
    logger.info("Shutting down application resources...")


def create_application() -> FastAPI:
    """Application factory for FastAPI instance."""
    app = FastAPI(
        title=settings.PROJECT_NAME,
        version="0.1.0",
        openapi_url=f"{settings.API_V1_STR}/openapi.json",
        docs_url=f"{settings.API_V1_STR}/docs",
        redoc_url=f"{settings.API_V1_STR}/redoc",
        lifespan=lifespan,
    )

    # Rate Limiter setup
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)

    # Cross-Origin Resource Sharing (CORS) setup
    allow_origins = [str(origin) for origin in settings.BACKEND_CORS_ORIGINS]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allow_origins if "*" not in allow_origins else [
            "http://localhost:3000",
            "http://localhost:5173",
            "http://localhost:5174",
            "http://127.0.0.1:3000",
            "http://127.0.0.1:5173",
            "http://localhost:8080",
        ],
        allow_origin_regex=r"https?://(localhost|127\.0\.0\.1)(:\d+)?" if "*" in allow_origins else None,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


    # API routers
    app.include_router(api_router, prefix=settings.API_V1_STR)

    @app.get("/", tags=["Root"], status_code=status.HTTP_200_OK)
    async def root():
        return JSONResponse(
            content={
                "message": f"Welcome to {settings.PROJECT_NAME}",
                "docs": f"{settings.API_V1_STR}/docs",
                "health": f"{settings.API_V1_STR}/health",
            }
        )

    return app


app = create_application()
