from fastapi import APIRouter, Request, status
from fastapi.responses import StreamingResponse

from app.api.v1.deps import CurrentUser, DatabaseSession
from app.core.rate_limit import limiter
from app.schemas.rag import QueryRequest, QueryResponse
from app.services.rag_service import RAGService

router = APIRouter()
rag_service = RAGService()


@router.post(
    "/query",
    response_model=QueryResponse,
    summary="Query RAG Knowledge Base",
    description="Multi-tenant RAG query endpoint. Supports streaming tokens via Server-Sent Events (SSE) or full JSON response.",
    responses={
        200: {
            "description": "SSE stream (text/event-stream) if stream=true, or JSON (application/json) if stream=false.",
            "content": {
                "text/event-stream": {
                    "example": "event: sources\ndata: {\"citations\": [...]}\n\nevent: token\ndata: {\"token\": \"The\"}\n\n"
                },
                "application/json": {},
            },
        }
    },
)
@limiter.limit("20/minute")
async def query_rag(
    request: Request,
    query_in: QueryRequest,
    current_user: CurrentUser,
    db: DatabaseSession,
):
    """Execute hybrid retrieval and generate tenant-scoped LLM response."""
    if query_in.stream:
        generator = rag_service.stream_rag_response(
            db=db,
            user_id=current_user.id,
            request=query_in,
        )
        return StreamingResponse(
            generator,
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
                "Content-Type": "text/event-stream",
            },
        )

    # Non-streaming complete JSON response
    return await rag_service.generate_response(
        db=db,
        user_id=current_user.id,
        request=query_in,
    )
