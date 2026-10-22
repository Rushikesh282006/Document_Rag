from typing import List, Optional
import uuid
from pydantic import BaseModel, Field


class QueryRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=2000, description="The user question or search prompt.")
    document_ids: Optional[List[uuid.UUID]] = Field(
        default=None,
        description="Optional list of document IDs to restrict retrieval to specific documents.",
    )
    top_k: int = Field(default=5, ge=1, le=20, description="Number of context chunks to retrieve.")
    stream: bool = Field(default=True, description="Whether to stream response tokens via Server-Sent Events (SSE).")


class Citation(BaseModel):
    document_id: uuid.UUID
    filename: str
    page_number: Optional[int] = None
    content_preview: str
    score: float


class QueryResponse(BaseModel):
    query: str
    answer: str
    citations: List[Citation]
