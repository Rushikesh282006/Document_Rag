import os
from pathlib import Path
from typing import List
import uuid

from fastapi import (
    APIRouter,
    File,
    HTTPException,
    Request,
    UploadFile,
    status,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import CurrentUser, DatabaseSession
from app.core.config import settings
from app.core.rate_limit import limiter
from app.models.document import Document, DocumentStatus
from app.schemas.document import DocumentResponse, UploadResponse
from app.worker.tasks import process_document_task

router = APIRouter()

MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024  # 50 MB limit


@router.post(
    "/upload",
    response_model=UploadResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Upload PDF Document",
    description="Asynchronously ingest a PDF document. Saves file and enqueues Celery background job.",
)
@limiter.limit("10/minute")
async def upload_document(
    request: Request,
    current_user: CurrentUser,
    db: DatabaseSession,
    file: UploadFile = File(..., description="PDF file to ingest"),
) -> UploadResponse:
    # 1. Validation
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only PDF files (.pdf) are supported.",
        )

    # 2. Prepare user storage directory
    user_storage_dir = Path(settings.UPLOAD_DIR) / str(current_user.id)
    user_storage_dir.mkdir(parents=True, exist_ok=True)

    file_uuid = uuid.uuid4()
    safe_filename = Path(file.filename).name
    saved_file_name = f"{file_uuid}_{safe_filename}"
    saved_file_path = user_storage_dir / saved_file_name

    # 3. Stream file to disk asynchronously without blocking the event loop
    file_size = 0
    try:
        with open(saved_file_path, "wb") as buffer:
            while chunk := await file.read(1024 * 1024):  # 1MB chunks
                file_size += len(chunk)
                if file_size > MAX_FILE_SIZE_BYTES:
                    # Cleanup partially written file
                    buffer.close()
                    if saved_file_path.exists():
                        saved_file_path.unlink()
                    raise HTTPException(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        detail=f"File exceeds maximum allowed size of {MAX_FILE_SIZE_BYTES // (1024 * 1024)}MB.",
                    )
                buffer.write(chunk)
    except HTTPException:
        raise
    except Exception as exc:
        if saved_file_path.exists():
            saved_file_path.unlink()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save file: {str(exc)}",
        )

    if file_size == 0:
        if saved_file_path.exists():
            saved_file_path.unlink()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The uploaded file is empty.",
        )

    # 4. Record Document in DB
    document = Document(
        id=file_uuid,
        user_id=current_user.id,
        filename=safe_filename,
        file_path=str(saved_file_path.resolve()),
        status=DocumentStatus.PENDING,
    )
    db.add(document)
    await db.commit()
    await db.refresh(document)

    # 5. Dispatch Celery task
    task = process_document_task.delay(str(document.id), str(current_user.id))

    return UploadResponse(
        job_id=task.id,
        document_id=document.id,
        filename=document.filename,
        status=document.status,
        message="Document uploaded successfully and queued for background processing.",
    )


@router.get(
    "",
    response_model=List[DocumentResponse],
    include_in_schema=False,
)
@router.get(
    "/",
    response_model=List[DocumentResponse],
    summary="List Documents",
    description="Retrieve all documents belonging to the authenticated tenant.",
)
async def list_documents(
    current_user: CurrentUser,
    db: DatabaseSession,
) -> List[DocumentResponse]:
    stmt = (
        select(Document)
        .where(Document.user_id == current_user.id)
        .order_by(Document.created_at.desc())
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


@router.get(
    "/{document_id}",
    response_model=DocumentResponse,
    summary="Get Document Status",
    description="Fetch document ingestion status and metadata for a specific document.",
)
async def get_document(
    document_id: uuid.UUID,
    current_user: CurrentUser,
    db: DatabaseSession,
) -> DocumentResponse:
    stmt = select(Document).where(
        Document.id == document_id,
        Document.user_id == current_user.id,
    )
    result = await db.execute(stmt)
    doc = result.scalar_one_or_none()

    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found.",
        )

    return doc


@router.delete(
    "/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete Document",
    description="Delete a document, its physical storage, and all associated vector chunks.",
)
async def delete_document(
    document_id: uuid.UUID,
    current_user: CurrentUser,
    db: DatabaseSession,
):
    stmt = select(Document).where(
        Document.id == document_id,
        Document.user_id == current_user.id,
    )
    result = await db.execute(stmt)
    doc = result.scalar_one_or_none()

    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found.",
        )

    # Delete physical file from disk
    file_path = Path(doc.file_path)
    if file_path.is_file():
        try:
            file_path.unlink()
        except OSError:
            pass

    # Delete document from database (cascades to chunks)
    await db.delete(doc)
    await db.commit()
    return None
