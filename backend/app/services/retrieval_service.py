from typing import Any, Dict, List, Optional
import uuid
import logging
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document, DocumentChunk
from app.schemas.rag import Citation
from app.services.embedding_service import EmbeddingService

logger = logging.getLogger(__name__)


class RetrievedChunk:
    def __init__(
        self,
        chunk: DocumentChunk,
        filename: str,
        score: float,
    ):
        self.chunk = chunk
        self.filename = filename
        self.score = score

    @property
    def citation(self) -> Citation:
        return Citation(
            document_id=self.chunk.document_id,
            filename=self.filename,
            page_number=self.chunk.page_number,
            content_preview=self.chunk.content[:200] + "..." if len(self.chunk.content) > 200 else self.chunk.content,
            score=round(self.score, 4),
        )


class HybridRetrievalService:
    """Multi-tenant hybrid retrieval using pgvector cosine similarity and PostgreSQL full-text search."""

    def __init__(self, embedding_service: Optional[EmbeddingService] = None):
        self.embedding_service = embedding_service or EmbeddingService()

    async def search(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        query: str,
        document_ids: Optional[List[uuid.UUID]] = None,
        top_k: int = 5,
        rrf_k: int = 60,
    ) -> List[RetrievedChunk]:
        """Perform multi-tenant hybrid search using Reciprocal Rank Fusion (RRF)."""
        fetch_limit = top_k * 2

        # 1. Vector similarity search
        query_embedding = self.embedding_service.generate_query_embedding(query)

        vector_filter = [
            DocumentChunk.user_id == user_id,
            DocumentChunk.embedding.isnot(None),
        ]
        if document_ids:
            vector_filter.append(DocumentChunk.document_id.in_(document_ids))

        vector_stmt = (
            select(DocumentChunk, Document.filename)
            .join(Document, DocumentChunk.document_id == Document.id)
            .where(*vector_filter)
            .order_by(DocumentChunk.embedding.cosine_distance(query_embedding))
            .limit(fetch_limit)
        )
        vector_res = await db.execute(vector_stmt)
        vector_matches = vector_res.all()

        # 2. Keyword / Full-Text Search (PostgreSQL tsvector)
        ts_query = func.plainto_tsquery("english", query)
        ts_vector = func.to_tsvector("english", DocumentChunk.content)

        keyword_filter = [
            DocumentChunk.user_id == user_id,
            ts_vector.op("@@")(ts_query),
        ]
        if document_ids:
            keyword_filter.append(DocumentChunk.document_id.in_(document_ids))

        keyword_stmt = (
            select(DocumentChunk, Document.filename)
            .join(Document, DocumentChunk.document_id == Document.id)
            .where(*keyword_filter)
            .order_by(func.ts_rank_cd(ts_vector, ts_query).desc())
            .limit(fetch_limit)
        )
        keyword_res = await db.execute(keyword_stmt)
        keyword_matches = keyword_res.all()

        # Fallback ILIKE if no tsquery matches found and query has terms
        if not keyword_matches:
            words = [w.strip() for w in query.split() if len(w.strip()) > 3]
            if words:
                ilike_conditions = [DocumentChunk.content.ilike(f"%{word}%") for word in words[:3]]
                ilike_filter = [
                    DocumentChunk.user_id == user_id,
                    *ilike_conditions,
                ]
                if document_ids:
                    ilike_filter.append(DocumentChunk.document_id.in_(document_ids))
                ilike_stmt = (
                    select(DocumentChunk, Document.filename)
                    .join(Document, DocumentChunk.document_id == Document.id)
                    .where(*ilike_filter)
                    .limit(fetch_limit)
                )
                ilike_res = await db.execute(ilike_stmt)
                keyword_matches = ilike_res.all()

        # 3. Reciprocal Rank Fusion (RRF)
        # score = sum(1 / (rrf_k + rank))
        chunk_map: Dict[uuid.UUID, tuple[DocumentChunk, str]] = {}
        rrf_scores: Dict[uuid.UUID, float] = {}

        for rank, (chunk, filename) in enumerate(vector_matches, start=1):
            chunk_map[chunk.id] = (chunk, filename)
            rrf_scores[chunk.id] = rrf_scores.get(chunk.id, 0.0) + (1.0 / (rrf_k + rank))

        for rank, (chunk, filename) in enumerate(keyword_matches, start=1):
            chunk_map[chunk.id] = (chunk, filename)
            rrf_scores[chunk.id] = rrf_scores.get(chunk.id, 0.0) + (1.0 / (rrf_k + rank))

        # Sort descending by fused RRF score
        sorted_chunk_ids = sorted(
            rrf_scores.keys(),
            key=lambda cid: rrf_scores[cid],
            reverse=True,
        )[:top_k]

        results: List[RetrievedChunk] = []
        for cid in sorted_chunk_ids:
            chunk, filename = chunk_map[cid]
            score = rrf_scores[cid]
            results.append(RetrievedChunk(chunk=chunk, filename=filename, score=score))

        return results
