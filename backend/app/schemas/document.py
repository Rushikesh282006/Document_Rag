from datetime import datetime
from typing import Optional, Dict, Any
import uuid
from pydantic import BaseModel, ConfigDict
from app.models.document import DocumentStatus


class DocumentBase(BaseModel):
    filename: str


class DocumentResponse(DocumentBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    file_path: str
    status: DocumentStatus
    error_message: Optional[str] = None
    created_at: datetime


class UploadResponse(BaseModel):
    job_id: str
    document_id: uuid.UUID
    filename: str
    status: DocumentStatus
    message: str


class DocumentChunkResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    document_id: uuid.UUID
    user_id: uuid.UUID
    content: str
    page_number: Optional[int] = None
    chunk_metadata: Dict[str, Any]
    created_at: datetime
