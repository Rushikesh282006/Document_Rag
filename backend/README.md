# Production-Ready Multi-Tenant RAG Backend API

A production-grade, asynchronous, multi-tenant Retrieval-Augmented Generation (RAG) backend API built with FastAPI, PostgreSQL (`pgvector`), Celery, Redis, and LangChain (supporting Google Gemini & OpenAI).

---

## Architecture Overview

```text
                                  +-------------------+
                                  |   FastAPI App     |
                                  +---------+---------+
                                            |
               +----------------------------+----------------------------+
               |                                                         |
         [Sync / Async]                                             [Async Job]
               |                                                         |
               v                                                         v
   +-----------------------+                                 +-----------------------+
   |   PostgreSQL + Vector |                                 |     Redis Broker      |
   |   (Tenancy, Metadata, |                                 +-----------+-----------+
   |    Embeddings, FTS)   |                                             |
   +-----------^-----------+                                             v
               |                                             +-----------------------+
               +---------------------------------------------+     Celery Worker     |
                                                             | (PDF Parser, Chunker, |
                                                             |  Embedding Generator) |
                                                             +-----------------------+
```

### Core Capabilities
- **Strict Multi-Tenancy**: Every document and embedding chunk is indexed by `user_id`. Queries strictly filter chunks owned by the authenticated tenant.
- **Non-Blocking Asynchronous Ingestion**: `POST /api/v1/documents/upload` stores the PDF and immediately returns `202 Accepted` with a Celery `job_id`.
- **Page-Aware Processing**: Background worker extracts text page-by-page, chunks with `RecursiveCharacterTextSplitter`, generates vector embeddings, and stores citations.
- **Hybrid Retrieval**: Combines semantic vector similarity (`pgvector` cosine distance) and lexical search (PostgreSQL `tsvector` full-text search) using **Reciprocal Rank Fusion (RRF)**.
- **Server-Sent Events (SSE) Streaming**: `POST /api/v1/query` uses `StreamingResponse` to stream the sources/citations first, followed by real-time LLM token deltas, ending with a completion event.
- **Dual LLM Provider Support**: Toggle seamlessly between **Google Gemini** (`gemini-1.5-flash` + `text-embedding-004`) and **OpenAI** (`gpt-4o-mini` + `text-embedding-3-small`).

---

## Quickstart

### 1. Environment Configuration

Copy the sample environment file:
```bash
cp .env.example .env
```

Set your API key in `.env`:
```env
GOOGLE_API_KEY="your-google-gemini-api-key"
# or
OPENAI_API_KEY="your-openai-api-key"
EMBEDDING_MODEL_PROVIDER="google" # or "openai"
LLM_MODEL_PROVIDER="google"       # or "openai"
```

### 2. Start Services via Docker Compose

Spin up PostgreSQL (with pgvector), Redis, FastAPI API, and Celery Worker:
```bash
docker compose up -d
```

Check logs:
```bash
docker compose logs -f web worker
```

### 3. Run Database Migrations

Apply Alembic migrations to create tables and enable the `vector` extension:
```bash
# If running locally with virtualenv:
alembic upgrade head

# Or inside the Docker container:
docker compose exec web alembic upgrade head
```

Interactive API documentation will be available at:
- Swagger UI: [http://localhost:8000/api/v1/docs](http://localhost:8000/api/v1/docs)
- ReDoc: [http://localhost:8000/api/v1/redoc](http://localhost:8000/api/v1/redoc)

---

## API Usage Walkthrough

### 1. Register and Authenticate

**Register:**
```bash
curl -X POST "http://localhost:8000/api/v1/auth/register" \
     -H "Content-Type: application/json" \
     -d '{"email": "user@example.com", "password": "SecretPassword123"}'
```

**Login:**
```bash
curl -X POST "http://localhost:8000/api/v1/auth/login" \
     -H "Content-Type: application/x-www-form-urlencoded" \
     -d "username=user@example.com&password=SecretPassword123"
```
Response:
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6...",
  "token_type": "bearer"
}
```

### 2. Upload Document (Non-Blocking)

```bash
curl -X POST "http://localhost:8000/api/v1/documents/upload" \
     -H "Authorization: Bearer <ACCESS_TOKEN>" \
     -F "file=@/path/to/sample.pdf"
```
Response (`202 Accepted`):
```json
{
  "job_id": "b3040375-397a-4ec6-89bf-9dfb58253fe9",
  "document_id": "3c985fa0-90c2-4eb9-a868-80f488ee279a",
  "filename": "sample.pdf",
  "status": "PENDING",
  "message": "Document uploaded successfully and queued for background processing."
}
```

**Check Processing Status:**
```bash
curl -X GET "http://localhost:8000/api/v1/documents/3c985fa0-90c2-4eb9-a868-80f488ee279a" \
     -H "Authorization: Bearer <ACCESS_TOKEN>"
```

### 3. Stream RAG Query (Server-Sent Events)

```bash
curl -N -X POST "http://localhost:8000/api/v1/query" \
     -H "Authorization: Bearer <ACCESS_TOKEN>" \
     -H "Content-Type: application/json" \
     -d '{
       "query": "What are the primary conclusions in the report?",
       "top_k": 5,
       "stream": true
     }'
```

**Sample SSE Event Stream:**
```text
event: sources
data: {"citations": [{"document_id": "3c985fa0-...", "filename": "sample.pdf", "page_number": 4, "content_preview": "In conclusion, the fiscal performance...", "score": 0.0328}]}

event: token
data: {"token": "Based"}

event: token
data: {"token": " on"}

event: token
data: {"token": " the"}

event: token
data: {"token": " report [Source: sample.pdf, Page 4]..."}

event: end
data: {"status": "completed"}
```
