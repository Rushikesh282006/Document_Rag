import json
import logging
from collections.abc import AsyncGenerator
from typing import Any, List, Optional
import uuid


from langchain_core.messages import HumanMessage, SystemMessage
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.rag import Citation, QueryRequest, QueryResponse
from app.services.llm_service import get_llm
from app.services.retrieval_service import HybridRetrievalService, RetrievedChunk

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a precise, reliable AI assistant answering questions based on the user's uploaded documents.
Use ONLY the provided context snippets below to answer the user's question.
Always provide inline citations where appropriate using the exact format: [Source: <filename>, Page: <page_number>].
If the provided context does not contain the information required to answer the question, clearly state: "I could not find the relevant information in your uploaded documents."
Do not speculate or extrapolate beyond what is documented."""


def _extract_text(content: Any) -> str:
    """Robustly extract plain text from string, list of parts/dicts, or structured objects."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                parts.append(item.get("text", ""))
        return "".join(parts)
    if isinstance(content, dict):
        return content.get("text", "")
    return str(content or "")


class RAGService:
    """Service to orchestrate hybrid retrieval and streaming LLM response generation."""

    def __init__(
        self,
        retrieval_service: Optional[HybridRetrievalService] = None,
    ):
        self.retrieval_service = retrieval_service or HybridRetrievalService()

    def _build_context_and_citations(
        self, retrieved_chunks: List[RetrievedChunk]
    ) -> tuple[str, List[Citation]]:
        """Construct the formatted context string and citations list."""
        context_parts: List[str] = []
        citations: List[Citation] = []

        for item in retrieved_chunks:
            page_info = f"Page {item.chunk.page_number}" if item.chunk.page_number else "Page N/A"
            header = f"[Source: {item.filename}, {page_info}]"
            context_parts.append(f"{header}\n{item.chunk.content}")
            citations.append(item.citation)

        context_str = "\n\n---\n\n".join(context_parts)
        return context_str, citations

    async def generate_response(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        request: QueryRequest,
    ) -> QueryResponse:
        """Non-streaming query execution."""
        # 1. Retrieve hybrid context
        retrieved_chunks = await self.retrieval_service.search(
            db=db,
            user_id=user_id,
            query=request.query,
            document_ids=request.document_ids,
            top_k=request.top_k,
        )

        if not retrieved_chunks:
            return QueryResponse(
                query=request.query,
                answer="No relevant documents found in your library for this query.",
                citations=[],
            )

        context_str, citations = self._build_context_and_citations(retrieved_chunks)

        # 2. Invoke LLM
        llm = get_llm()
        messages = [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(
                content=f"Context from documents:\n{context_str}\n\nQuestion: {request.query}"
            ),
        ]

        response = await llm.ainvoke(messages)
        answer_text = _extract_text(response.content)

        return QueryResponse(
            query=request.query,
            answer=answer_text,
            citations=citations,
        )

    async def stream_rag_response(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        request: QueryRequest,
    ) -> AsyncGenerator[str, None]:
        """Stream RAG response tokens via Server-Sent Events (SSE)."""
        try:
            # 1. Hybrid Retrieval
            retrieved_chunks = await self.retrieval_service.search(
                db=db,
                user_id=user_id,
                query=request.query,
                document_ids=request.document_ids,
                top_k=request.top_k,
            )

            if not retrieved_chunks:
                # Emit empty citations
                sources_payload = json.dumps({"citations": []})
                yield f"event: sources\ndata: {sources_payload}\n\n"

                msg_payload = json.dumps(
                    {"token": "No relevant documents found in your uploaded library to answer this question."}
                )
                yield f"event: token\ndata: {msg_payload}\n\n"

                done_payload = json.dumps({"status": "completed"})
                yield f"event: end\ndata: {done_payload}\n\n"
                return

            context_str, citations = self._build_context_and_citations(retrieved_chunks)

            # 2. Emit citations/sources metadata event first
            citations_dict = [c.model_dump(mode="json") for c in citations]
            sources_payload = json.dumps({"citations": citations_dict})
            yield f"event: sources\ndata: {sources_payload}\n\n"

            # 3. Stream LLM generated tokens
            llm = get_llm()
            messages = [
                SystemMessage(content=SYSTEM_PROMPT),
                HumanMessage(
                    content=f"Context from documents:\n{context_str}\n\nQuestion: {request.query}"
                ),
            ]

            async for chunk in llm.astream(messages):
                token_text = _extract_text(chunk.content)
                if token_text:
                    token_payload = json.dumps({"token": token_text})
                    yield f"event: token\ndata: {token_payload}\n\n"

            # 4. Emit end of stream event
            done_payload = json.dumps({"status": "completed"})
            yield f"event: end\ndata: {done_payload}\n\n"

        except Exception as exc:
            logger.exception(f"Error streaming RAG response: {exc}")
            err_payload = json.dumps({"error": str(exc)})
            yield f"event: error\ndata: {err_payload}\n\n"
