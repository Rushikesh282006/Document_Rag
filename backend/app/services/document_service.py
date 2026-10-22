import logging
from pathlib import Path
from typing import Any, Dict, List, Tuple
import uuid
from pypdf import PdfReader
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

try:
    from langchain_text_splitters import RecursiveCharacterTextSplitter
except ImportError:
    from langchain.text_splitter import RecursiveCharacterTextSplitter

from app.core.database import AsyncWorkerSessionLocal
from app.models.document import Document, DocumentChunk, DocumentStatus
from app.services.embedding_service import EmbeddingService


logger = logging.getLogger(__name__)


class DocumentProcessingService:
    """Service to extract text, chunk content, generate embeddings, and store chunks."""

    def __init__(self, chunk_size: int = 1000, chunk_overlap: int = 200):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            separators=["\n\n", "\n", ". ", " ", ""],
            length_function=len,
        )

    def extract_pdf_pages(self, file_path: str) -> List[Tuple[str, int]]:
        """Extract text from PDF file preserving 1-indexed page numbers."""
        path = Path(file_path)
        if not path.is_file():
            raise FileNotFoundError(f"File not found at: {file_path}")

        reader = PdfReader(str(path))
        pages_content: List[Tuple[str, int]] = []

        for index, page in enumerate(reader.pages):
            page_text = page.extract_text() or ""
            cleaned_text = page_text.strip()
            if cleaned_text:
                pages_content.append((cleaned_text, index + 1))

        return pages_content

    def chunk_extracted_content(
        self, pages_data: List[Tuple[str, int]], source_filename: str
    ) -> List[Dict[str, Any]]:
        """Split page texts into semantic chunks with provenance metadata."""
        chunks: List[Dict[str, Any]] = []
        chunk_counter = 0

        for text, page_number in pages_data:
            split_texts = self.text_splitter.split_text(text)
            for split_text in split_texts:
                if not split_text.strip():
                    continue
                chunks.append(
                    {
                        "content": split_text,
                        "page_number": page_number,
                        "metadata": {
                            "source": source_filename,
                            "page": page_number,
                            "chunk_index": chunk_counter,
                        },
                    }
                )
                chunk_counter += 1

        return chunks

    async def execute_pipeline(self, document_id_str: str, user_id_str: str) -> None:
        """Asynchronous execution pipeline for a queued document ingestion job."""
        doc_uuid = uuid.UUID(document_id_str)
        user_uuid = uuid.UUID(user_id_str)

        async with AsyncWorkerSessionLocal() as session:
            try:
                # 1. Fetch document and update to PROCESSING
                stmt = select(Document).where(
                    Document.id == doc_uuid,
                    Document.user_id == user_uuid,
                )
                result = await session.execute(stmt)
                document = result.scalar_one_or_none()

                if not document:
                    logger.error(f"Document {doc_uuid} for user {user_uuid} not found.")
                    return

                document.status = DocumentStatus.PROCESSING
                document.error_message = None
                await session.commit()
                logger.info(f"Started processing document {doc_uuid} ({document.filename})")

                # 2. Extract PDF text per page
                pages_data = self.extract_pdf_pages(document.file_path)
                if not pages_data:
                    document.status = DocumentStatus.FAILED
                    document.error_message = "No readable text found in document."
                    await session.commit()
                    logger.warning(f"No text extracted for document {doc_uuid}")
                    return

                # 3. Chunk text content
                chunks_data = self.chunk_extracted_content(pages_data, document.filename)
                if not chunks_data:
                    document.status = DocumentStatus.FAILED
                    document.error_message = "Text chunking produced zero segments."
                    await session.commit()
                    return

                # 4. Generate embeddings
                logger.info(f"Generating embeddings for {len(chunks_data)} chunks...")
                embedding_service = EmbeddingService()
                texts = [c["content"] for c in chunks_data]
                embeddings = embedding_service.generate_embeddings(texts)

                # 5. Persist document chunks
                chunk_records: List[DocumentChunk] = []
                for i, chunk_info in enumerate(chunks_data):
                    chunk_records.append(
                        DocumentChunk(
                            id=uuid.uuid4(),
                            document_id=doc_uuid,
                            user_id=user_uuid,
                            content=chunk_info["content"],
                            page_number=chunk_info["page_number"],
                            embedding=embeddings[i] if i < len(embeddings) else None,
                            chunk_metadata=chunk_info["metadata"],
                        )
                    )

                session.add_all(chunk_records)

                # 6. Mark document as COMPLETED
                document.status = DocumentStatus.COMPLETED
                document.error_message = None
                await session.commit()
                logger.info(f"Successfully processed and embedded document {doc_uuid} ({len(chunk_records)} chunks)")

            except Exception as exc:
                logger.exception(f"Error occurred while processing document {doc_uuid}: {exc}")
                await session.rollback()

                # Record failure on document
                async with AsyncWorkerSessionLocal() as err_session:
                    err_stmt = select(Document).where(Document.id == doc_uuid)
                    err_res = await err_session.execute(err_stmt)
                    doc_to_fail = err_res.scalar_one_or_none()
                    if doc_to_fail:
                        doc_to_fail.status = DocumentStatus.FAILED
                        doc_to_fail.error_message = str(exc)
                        await err_session.commit()
                raise exc

