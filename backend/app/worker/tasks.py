import asyncio
import logging
from celery import shared_task
from app.worker.celery_app import celery_app
from app.services.document_service import DocumentProcessingService

logger = logging.getLogger(__name__)


@celery_app.task(
    name="process_document_task",
    bind=True,
    max_retries=3,
    default_retry_delay=10,
    acks_late=True,
)
def process_document_task(self, document_id: str, user_id: str) -> dict:
    """Celery background worker task to process and embed an uploaded document."""
    logger.info(f"[Task {self.request.id}] Starting processing for document {document_id}")
    service = DocumentProcessingService()

    try:
        # Run async pipeline inside event loop
        asyncio.run(service.execute_pipeline(document_id, user_id))
        logger.info(f"[Task {self.request.id}] Document {document_id} ingestion succeeded.")
        return {
            "status": "success",
            "document_id": document_id,
            "user_id": user_id,
        }
    except Exception as exc:
        logger.error(f"[Task {self.request.id}] Error processing document {document_id}: {exc}")
        # Retry for transient failures
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc)
        raise exc
