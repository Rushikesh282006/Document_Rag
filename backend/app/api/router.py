from fastapi import APIRouter
from app.api.v1.endpoints import auth, documents, health, rag

api_router = APIRouter()

# Health router
api_router.include_router(health.router, tags=["Health"])

# Authentication router
api_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])

# Documents ingestion & management router
api_router.include_router(documents.router, prefix="/documents", tags=["Documents"])

# RAG Query & Streaming router (/api/v1/rag/query and alias /api/v1/query)
api_router.include_router(rag.router, prefix="/rag", tags=["RAG"])
api_router.include_router(rag.router, tags=["RAG"])



