import logging
from fastapi import Request, Response
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.core.config import settings

logger = logging.getLogger(__name__)


def get_client_identifier(request: Request) -> str:
    """Extract a unique client identifier for rate limiting.
    
    If the request has an Authorization header, uses the token.
    Otherwise, falls back to the client IP address.
    """
    auth = request.headers.get("Authorization")
    if auth and auth.startswith("Bearer "):
        token = auth.split("Bearer ", 1)[1].strip()
        if token:
            # Hash or truncate token prefix to use as consistent user-level key
            return f"user:{token[:32]}"
    
    return get_remote_address(request)


# Initialize Redis-backed limiter with graceful in-memory fallback
_storage_uri = settings.CELERY_BROKER_URL or "redis://localhost:6379/0"

try:
    limiter = Limiter(
        key_func=get_client_identifier,
        storage_uri=_storage_uri,
        strategy="moving-window",
    )
    logger.info(f"Rate limiter initialized with Redis backend: {_storage_uri}")
except Exception as err:
    logger.warning(f"Failed to connect rate limiter to Redis ({err}). Falling back to memory storage.")
    limiter = Limiter(
        key_func=get_client_identifier,
        strategy="moving-window",
    )


def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded) -> Response:
    """Generate consistent HTTP 429 JSON response when rate limit is exceeded."""
    client_id = get_client_identifier(request)
    logger.warning(
        f"Rate limit exceeded on '{request.method} {request.url.path}' by '{client_id}': {exc.detail}"
    )
    
    response = JSONResponse(
        status_code=429,
        content={
            "detail": f"Rate limit exceeded: {exc.detail}. Please wait before making more requests.",
            "error": "rate_limit_exceeded",
        },
    )
    response.headers["Retry-After"] = "60"
    return response
