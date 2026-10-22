# Groundwork: Multi-Tenant Document RAG Platform

[![FastAPI](https://img.shields.io/badge/FastAPI-0.111+-009688?style=flat-square&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16%20+%20pgvector-336791?style=flat-square&logo=postgresql&logoColor=white)](https://github.com/pgvector/pgvector)
[![Celery](https://img.shields.io/badge/Celery-5.4+-37814A?style=flat-square&logo=celery&logoColor=white)](https://docs.celeryq.dev)
[![Redis](https://img.shields.io/badge/Redis-7+-DC382D?style=flat-square&logo=redis&logoColor=white)](https://redis.io)
[![React](https://img.shields.io/badge/React-19-61DAFB?style=flat-square&logo=react&logoColor=black)](https://react.dev)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.8+-3178C6?style=flat-square&logo=typescript&logoColor=white)](https://www.typescriptlang.org)
[![Vite](https://img.shields.io/badge/Vite-8.1+-646CFF?style=flat-square&logo=vite&logoColor=white)](https://vitejs.dev)
[![Tailwind CSS](https://img.shields.io/badge/Tailwind_CSS-v4-06B6D4?style=flat-square&logo=tailwindcss&logoColor=white)](https://tailwindcss.com)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?style=flat-square&logo=docker&logoColor=white)](https://www.docker.com)

A high-performance, production-grade, multi-tenant Retrieval-Augmented Generation (RAG) platform. Groundwork couples an asynchronous **FastAPI + PostgreSQL (`pgvector`) + Celery + Redis** backend with a responsive **React 19 + TanStack Router + Tailwind CSS** frontend to provide grounded, citation-backed document search and conversational AI with real-time token streaming.

---

## Table of Contents

- [Key Features](#key-features)
- [System Architecture](#system-architecture)
  - [High-Level Architecture](#high-level-architecture)
  - [Ingestion Pipeline](#ingestion-pipeline)
  - [Hybrid Retrieval & Generation Pipeline](#hybrid-retrieval--generation-pipeline)
- [Tech Stack](#tech-stack)
- [Repository Structure](#repository-structure)
- [Prerequisites](#prerequisites)
- [Quick Start Guide](#quick-start-guide)
  - [Option A: Docker Compose (Backend) + Local Frontend](#option-a-docker-compose-backend--local-frontend)
  - [Option B: Fully Local Development Setup](#option-b-fully-local-development-setup)
- [Environment Configuration](#environment-configuration)
  - [Backend Environment Variables (`backend/.env`)](#backend-environment-variables-backendenv)
  - [Frontend Environment Variables (`frontend/.env`)](#frontend-environment-variables-frontendenv)
- [API Reference & Usage](#api-reference--usage)
  - [1. Authentication](#1-authentication)
  - [2. Document Ingestion & Management](#2-document-ingestion--management)
  - [3. RAG Query & Streaming](#3-rag-query--streaming)
- [Hybrid Search & Reciprocal Rank Fusion (RRF)](#hybrid-search--reciprocal-rank-fusion-rrf)
- [Frontend Capabilities & UI Features](#frontend-capabilities--ui-features)
- [Testing & Quality Assurance](#testing--quality-assurance)
- [Production Deployment](#production-deployment)
- [License](#license)

---

## Key Features

- **Strict Tenant Isolation**: Multi-tenant architecture from the database layer up. Documents, chunks, and vector embeddings are indexed and strictly filtered by tenant `user_id`.
- **Non-Blocking Ingestion**: PDF uploads return `202 Accepted` immediately with a Celery task `job_id`, offloading CPU-intensive text extraction, chunking, and embedding generation to background workers.
- **Page-Aware Chunking & Citations**: Documents are parsed page by page using `pypdf` and `pdfplumber`, chunked with `RecursiveCharacterTextSplitter`, and preserved with page-level citations.
- **Hybrid Retrieval (RRF)**: Merges dense vector embeddings (`pgvector` cosine similarity) with sparse lexical search (PostgreSQL `tsvector` full-text search) using Reciprocal Rank Fusion for optimal precision and recall.
- **Real-Time Token Streaming**: Server-Sent Events (SSE) stream verified citations upfront, followed by real-time LLM token generation, culminating in a completion status event.
- **Pluggable LLM & Embedding Ecosystem**:
  - **LLM Providers**: Google Gemini (`gemini-1.5-flash`), Groq (`llama-3.3-70b-versatile`), and OpenAI (`gpt-4o-mini`).
  - **Embedding Providers**: Google (`text-embedding-004`), HuggingFace (`BAAI/bge-base-en-v1.5`), and OpenAI (`text-embedding-3-small`).
- **Modern User Experience**:
  - React 19 single-page application with responsive desktop and mobile drawers.
  - Interactive Citation Inspector with relevance score meters and quote context.
  - Scoped document selection (chat against specific files or the entire library).
  - Built-in Mock/Live mode toggle for offline demonstration or testing against real endpoints.
- **Enterprise Controls**: Built-in rate limiting (SlowAPI), JWT authentication with bcrypt password hashing, and Alembic database versioning.

---

## System Architecture

### High-Level Architecture

```
                                  ┌────────────────────────┐
                                  │   React 19 Frontend    │
                                  │ (TanStack Router, SSE) │
                                  └───────────┬────────────┘
                                              │ HTTP / SSE (Bearer JWT)
                                              ▼
                                  ┌────────────────────────┐
                                  │   FastAPI Web API      │
                                  │  (Auth, CORS, Limiter) │
                                  └─────┬────────────┬─────┘
                                        │            │
                         Upload (Async) │            │ Sync / Read
                                        ▼            ▼
             ┌──────────────────────────────┐    ┌───────────────────────────────────┐
             │         Redis Queue          │    │       PostgreSQL 16 + pgvector    │
             └──────────────┬───────────────┘    │  - Tenants (Users)                │
                            │                    │  - Documents & Ingestion Status   │
                            ▼                    │  - Chunks, Embeddings, tsvectors  │
             ┌──────────────────────────────┐    └─────────────────▲─────────────────┘
             │        Celery Worker         │                      │
             │  - PDF Text Extraction       │                      │ Read / Write
             │  - Semantic Chunking         ├──────────────────────┘
             │  - Embedding Generation      │
             └──────────────────────────────┘
```

### Ingestion Pipeline

```
[User PDF Upload]
       │
       ▼
1. FastAPI validates PDF format & file size (up to 50MB)
       │
       ▼
2. File streamed to disk (`/uploads/<user_id>/<file_uuid>_<filename>`)
       │
       ▼
3. Record created in PostgreSQL with status = PENDING
       │
       ▼
4. Celery background task dispatched (`process_document_task`) -> Returns 202 Accepted
       │
       ▼ [Celery Worker Execution]
5. Status -> PROCESSING
6. Extract text page-by-page (pypdf/pdfplumber fallback)
7. Chunk text with RecursiveCharacterTextSplitter (chunk_size=1000, overlap=200)
8. Batch generate embeddings via Gemini / HuggingFace / OpenAI
9. Persist chunks & vector embeddings in PostgreSQL (pgvector)
10. Status -> COMPLETED (or FAILED on error)
```

### Hybrid Retrieval & Generation Pipeline

```
[User Chat Query]
       │
       ▼
1. Generate query embedding vector via EmbeddingService
       │
       ├─────────────────────────────────┬─────────────────────────────────┐
       ▼                                 ▼                                 ▼
   [Vector Search]              [Full-Text Search]                [Tenant Filter]
   pgvector cosine distance     PostgreSQL tsvector match        Strict user_id match
   limit = top_k * 2            limit = top_k * 2                + optional doc IDs
       │                                 │                                 │
       └────────────────┬────────────────┘                                 │
                        ▼                                                  │
2. Reciprocal Rank Fusion (RRF) ───────────────────────────────────────────┘
   Score = 1/(60 + vector_rank) + 1/(60 + fts_rank)
       │
       ▼
3. Select Top K ranked chunks & compile structured context with page numbers
       │
       ▼
4. Stream SSE Response:
   ├── Event 1: `event: sources` (Citations with document_id, filename, page, score, preview)
   ├── Event 2..N: `event: token` (Live LLM streaming tokens)
   └── Event Final: `event: end` (Status confirmation)
```

---

## Tech Stack

### Backend
| Technology | Role |
| :--- | :--- |
| **Python 3.11+** | Runtime environment |
| **FastAPI** | Asynchronous REST and SSE streaming web framework |
| **SQLAlchemy 2.0 (asyncpg)** | Async ORM and database connection pooling |
| **PostgreSQL 16 + pgvector** | Relational store with vector similarity search and Full-Text Search (`tsvector`) |
| **Celery** | Asynchronous distributed task queue for heavy PDF ingestion |
| **Redis 7** | Message broker for Celery and in-memory rate limiting backend |
| **Alembic** | Database migrations and vector extension setup |
| **LangChain / Google GenAI / Groq / OpenAI** | Multi-model orchestration, vector embeddings, and LLM completions |
| **PyPDF / PDFPlumber** | Robust PDF parsing and page-by-page text extraction |
| **SlowAPI** | In-flight request throttling and rate limiting |

### Frontend
| Technology | Role |
| :--- | :--- |
| **React 19** | Component framework |
| **TypeScript 5.8** | Type-safe client development |
| **Vite 8** | Ultra-fast development server and production bundler |
| **TanStack Router / Start** | Type-safe client-side and server-ready routing |
| **Tailwind CSS v4** | Utility-first styling engine with theme variables |
| **Radix UI** | Accessible primitive components (Dialog, Sheet, Dropdown, Accordion) |
| **Lucide React** | Consistent vector iconography |
| **React Markdown + Rehype** | GitHub Flavored Markdown and code syntax highlighting |

---

## Repository Structure

```text
Document_Rag/
├── backend/
│   ├── app/
│   │   ├── api/                      # Route controllers & dependencies
│   │   │   ├── v1/
│   │   │   │   ├── endpoints/
│   │   │   │   │   ├── auth.py       # Login, register, me endpoints
│   │   │   │   │   ├── documents.py  # Upload, list, status, delete endpoints
│   │   │   │   │   ├── health.py     # System health checks
│   │   │   │   │   └── rag.py        # Hybrid query & SSE stream endpoints
│   │   │   │   └── deps.py           # Dependency injection (Auth, DB session)
│   │   │   └── router.py             # Top-level API router aggregator
│   │   ├── core/                     # Application configurations & security
│   │   │   ├── config.py             # Pydantic BaseSettings & env resolution
│   │   │   ├── rate_limit.py         # SlowAPI rate limiter configuration
│   │   │   └── security.py           # JWT generation, validation, bcrypt hashing
│   │   ├── db/                       # Database session & base engine
│   │   │   └── session.py            # Async engine and sessionmaker
│   │   ├── models/                   # SQLAlchemy declarative models
│   │   │   ├── document.py           # Document & DocumentChunk (pgvector)
│   │   │   └── user.py               # User tenant model
│   │   ├── schemas/                  # Pydantic request & response schemas
│   │   ├── services/                 # Business logic services
│   │   │   ├── document_service.py   # PDF text extraction & chunking
│   │   │   ├── embedding_service.py  # Gemini / HuggingFace / OpenAI embeddings
│   │   │   ├── llm_service.py        # Gemini / Groq / OpenAI LLM invocations
│   │   │   ├── rag_service.py        # RAG orchestration & SSE token generator
│   │   │   └── retrieval_service.py  # Vector + FTS Reciprocal Rank Fusion
│   │   ├── worker/                   # Celery worker configuration & tasks
│   │   │   ├── celery_app.py         # Celery instance & broker configuration
│   │   │   └── tasks.py              # Asynchronous document processing task
│   │   └── main.py                   # FastAPI initialization, CORS, lifespan
│   ├── migrations/                   # Alembic schema migrations
│   ├── tests/                        # Pytest backend test suite
│   ├── uploads/                      # Local PDF document storage
│   ├── .env.example                  # Environment template
│   ├── docker-compose.yml            # Local development orchestration
│   ├── docker-compose.prod.yml       # Production container orchestration
│   ├── Dockerfile                    # Multi-stage backend container definition
│   └── requirements.txt              # Python library dependencies
│
├── frontend/
│   ├── public/                       # Static assets
│   ├── src/
│   │   ├── components/               # UI components
│   │   │   ├── ui/                   # Radix UI + Tailwind design components
│   │   │   ├── workspace/
│   │   │   │   ├── Chat.tsx          # Chat thread, SSE parser & message stream
│   │   │   │   └── DocumentSidebar.tsx # PDF upload, list, filter & delete
│   │   │   ├── AuthForm.tsx          # Login & registration forms
│   │   │   └── ModeSwitch.tsx        # Live API vs. Mock demonstration toggle
│   │   ├── hooks/                    # Custom React hooks (e.g. mobile detection)
│   │   ├── lib/
│   │   │   ├── api.ts                # API client with Mock fallback & SSE stream
│   │   │   ├── auth.tsx              # React Context for tenant authentication
│   │   │   └── utils.ts              # Styling and formatting utility helpers
│   │   ├── routes/                   # TanStack file-based routes
│   │   │   ├── __root.tsx            # Global layout shell & HTML head
│   │   │   ├── index.tsx             # Main workspace interface
│   │   │   ├── login.tsx             # Tenant login page
│   │   │   └── register.tsx          # Tenant sign-up page
│   │   └── styles.css                # Tailwind CSS v4 design tokens & themes
│   ├── .env.example                  # Frontend environment template
│   ├── package.json                  # Node dependencies & npm scripts
│   └── vite.config.ts                # Vite build and plugin configuration
│
└── README.md                         # Project documentation
```

---

## Prerequisites

Make sure you have the following installed on your machine:
- **Docker & Docker Compose** (Recommended): [Get Docker](https://docs.docker.com/get-docker/)
- **Python 3.11+** (for manual local backend runs): [Python Downloads](https://www.python.org/downloads/)
- **Node.js 18+ or 20+** and **npm** / **bun** (for frontend development): [Node.js Downloads](https://nodejs.org/)

---

## Quick Start Guide

### Option A: Docker Compose (Backend) + Local Frontend

This is the fastest and most convenient method to spin up the complete backend stack (PostgreSQL with `pgvector`, Redis, FastAPI, and Celery worker) with a single command.

#### 1. Start the Backend Containers
```bash
# Navigate to the backend directory
cd backend

# Copy environment template
cp .env.example .env

# Configure your API keys (e.g. GOOGLE_API_KEY, GROQ_API_KEY, or OPENAI_API_KEY) in .env
# Then build and start all 4 services:
docker compose up -d --build
```

#### 2. Run Database Migrations
Apply Alembic migrations inside the running API container:
```bash
docker compose exec web alembic upgrade head
```

Verify backend services:
- **FastAPI Swagger UI**: [http://localhost:8000/api/v1/docs](http://localhost:8000/api/v1/docs)
- **Health Check**: [http://localhost:8000/api/v1/health](http://localhost:8000/api/v1/health)

#### 3. Start the Frontend Application
Open a new terminal window:
```bash
# Navigate to the frontend directory
cd frontend

# Copy environment template
cp .env.example .env

# Install dependencies
npm install

# Start Vite development server
npm run dev
```

Visit the application at: [http://localhost:5173](http://localhost:5173) (or the port displayed in the console).

---

### Option B: Fully Local Development Setup

If you prefer to run Python and background services directly on your host machine:

#### 1. Start PostgreSQL with pgvector and Redis
You can use lightweight standalone Docker containers for the database and broker:
```bash
docker run -d --name rag_postgres -p 5432:5432 -e POSTGRES_USER=postgres -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=rag_db pgvector/pgvector:pg16
docker run -d --name rag_redis -p 6379:6379 redis:7-alpine
```

#### 2. Setup the Python Environment
```bash
cd backend

# Create and activate virtual environment
python -m venv .venv

# On Linux/macOS:
source .venv/bin/activate
# On Windows (PowerShell):
.venv\Scripts\Activate.ps1

# Upgrade pip and install dependencies
pip install --upgrade pip
pip install -r requirements.txt

# Copy .env and configure credentials
cp .env.example .env

# Apply database migrations
alembic upgrade head
```

#### 3. Start the FastAPI API Server
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

#### 4. Start the Celery Worker (in a separate terminal)
```bash
cd backend
# Make sure your virtual environment is activated
celery -A app.worker.celery_app.celery_app worker --loglevel=info -c 4
```

#### 5. Launch the Frontend
```bash
cd frontend
npm install
npm run dev
```

---

## Environment Configuration

### Backend Environment Variables (`backend/.env`)

| Variable | Default Value | Description |
| :--- | :--- | :--- |
| `ENVIRONMENT` | `development` | Deployment environment (`development` or `production`) |
| `DEBUG` | `True` | Enables debug logging and detailed errors |
| `PROJECT_NAME` | `Multi-Tenant RAG API` | OpenAPI application title |
| `API_V1_STR` | `/api/v1` | Base API prefix |
| `SECRET_KEY` | `change-me-...` | Secret key used for signing JWT tokens |
| `ALGORITHM` | `HS256` | JWT encoding algorithm |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `60` | Token expiration time in minutes |
| `DATABASE_URL` | `postgresql+asyncpg://postgres:postgres@localhost:5432/rag_db` | Async database connection URL |
| `CELERY_BROKER_URL` | `redis://localhost:6379/0` | Redis connection URL for Celery job queues |
| `CELERY_RESULT_BACKEND` | `redis://localhost:6379/0` | Redis connection URL for Celery task results |
| `UPLOAD_DIR` | `./uploads` | Filesystem storage path for uploaded PDF files |
| `LLM_MODEL_PROVIDER` | `groq` | Active LLM provider (`google`, `groq`, or `openai`) |
| `EMBEDDING_MODEL_PROVIDER` | `huggingface` | Active embedding provider (`google`, `huggingface`, or `openai`) |
| `EMBEDDING_DIMENSION` | `768` | Vector dimension size (768 for Gemini & BAAI, 1536 for OpenAI) |
| `GOOGLE_API_KEY` | `""` | Google Gemini API Key |
| `OPENAI_API_KEY` | `""` | OpenAI API Key |
| `GROQ_API_KEY` | `""` | Groq API Key |
| `GROQ_MODEL` | `llama-3.3-70b-versatile`| Groq model designation |
| `HUGGINGFACE_API_KEY` | `""` | Optional HuggingFace Token (for private models or higher rate limits) |
| `HUGGINGFACE_EMBEDDING_MODEL`| `BAAI/bge-base-en-v1.5` | Hugging Face embedding model path |

### Frontend Environment Variables (`frontend/.env`)

| Variable | Default Value | Description |
| :--- | :--- | :--- |
| `VITE_API_BASE_URL` | `http://localhost:8000/api/v1` | URL pointing to the FastAPI backend API |

---

## API Reference & Usage

### 1. Authentication

#### Register Tenant
```bash
curl -X POST "http://localhost:8000/api/v1/auth/register" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "researcher@example.com",
    "password": "SecurePassword123!"
  }'
```

#### Login & Retrieve JWT
```bash
curl -X POST "http://localhost:8000/api/v1/auth/login" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=researcher@example.com&password=SecurePassword123!"
```
*Response (`200 OK`):*
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer"
}
```

#### Fetch Current User Profile
```bash
curl -X GET "http://localhost:8000/api/v1/auth/me" \
  -H "Authorization: Bearer <ACCESS_TOKEN>"
```

---

### 2. Document Ingestion & Management

#### Upload PDF (Non-Blocking)
Upload a document. The endpoint validates the file, saves it securely, enqueues the background job, and immediately returns a `202 Accepted` status:
```bash
curl -X POST "http://localhost:8000/api/v1/documents/upload" \
  -H "Authorization: Bearer <ACCESS_TOKEN>" \
  -F "file=@/path/to/quarterly_report.pdf"
```
*Response (`202 Accepted`):*
```json
{
  "job_id": "8d39f705-728b-4a57-b08e-1f7c3c52e461",
  "document_id": "c1f7b820-e2b2-4db1-8669-df427e4e135e",
  "filename": "quarterly_report.pdf",
  "status": "PENDING",
  "message": "Document uploaded successfully and queued for background processing."
}
```

#### List Tenant Documents
```bash
curl -X GET "http://localhost:8000/api/v1/documents" \
  -H "Authorization: Bearer <ACCESS_TOKEN>"
```

#### Get Document Ingestion Status
```bash
curl -X GET "http://localhost:8000/api/v1/documents/c1f7b820-e2b2-4db1-8669-df427e4e135e" \
  -H "Authorization: Bearer <ACCESS_TOKEN>"
```

#### Delete Document & Associated Chunks
```bash
curl -X DELETE "http://localhost:8000/api/v1/documents/c1f7b820-e2b2-4db1-8669-df427e4e135e" \
  -H "Authorization: Bearer <ACCESS_TOKEN>"
```

---

### 3. RAG Query & Streaming

#### Stream Query Results (Server-Sent Events)
Sends a question with citation retrieval and real-time LLM token generation:
```bash
curl -N -X POST "http://localhost:8000/api/v1/query" \
  -H "Authorization: Bearer <ACCESS_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What were the primary revenue drivers according to page 3?",
    "document_ids": ["c1f7b820-e2b2-4db1-8669-df427e4e135e"],
    "top_k": 5,
    "stream": true
  }'
```

*Sample SSE Stream:*
```text
event: sources
data: {"citations": [{"document_id": "c1f7b820-...", "filename": "quarterly_report.pdf", "page_number": 3, "content_preview": "Cloud enterprise subscriptions grew 42% year-over-year...", "score": 0.0328}]}

event: token
data: {"token": "According"}

event: token
data: {"token": " to"}

event: token
data: {"token": " the"}

event: token
data: {"token": " quarterly report [Source: quarterly_report.pdf, Page 3], revenue was driven by..."}

event: end
data: {"status": "completed"}
```

#### Standard Non-Streaming JSON Query
Set `"stream": false` to receive the full payload at once:
```bash
curl -X POST "http://localhost:8000/api/v1/query" \
  -H "Authorization: Bearer <ACCESS_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Summarize the key risks outlined in the document.",
    "top_k": 3,
    "stream": false
  }'
```

---

## Hybrid Search & Reciprocal Rank Fusion (RRF)

Standard vector search can struggle with exact keyword queries (such as product SKUs, acronyms, or specific numbers), while lexical full-text search misses semantic intent. Groundwork bridges this gap using **Reciprocal Rank Fusion (RRF)**:

1. **Semantic Vector Search**: Generates query embeddings and computes the cosine distance using `pgvector`:
   $$\text{cosine\_distance} = 1 - \frac{u \cdot v}{\|u\|_2 \|v\|_2}$$
2. **Lexical Full-Text Search**: Uses PostgreSQL's English stemming dictionary (`to_tsvector` and `plainto_tsquery`) to rank chunks based on keyword matching:
   $$\text{ts\_rank\_cd}(tsvector, tsquery)$$
3. **Fusion Scoring**: Combines results from both search passes across candidate chunks using the standard RRF formula with constant $k = 60$:
   $$RRF(d) = \sum_{m \in M} \frac{1}{k + r_m(d)}$$
   *where $r_m(d)$ is the rank position of document chunk $d$ in system $m$.*
4. **Tenant Scoping**: All retrieval queries enforce `user_id = current_user.id`, guaranteeing zero cross-tenant data leakage.

---

## Frontend Capabilities & UI Features

- **Document Knowledge Base Sidebar**:
  - Drag-and-drop or file selector PDF uploads with 50MB validation.
  - Live status tracking with real-time badges: `PENDING`, `PROCESSING`, `COMPLETED`, `FAILED`.
  - Checkbox selection to dynamically scope queries to one, many, or all uploaded PDFs.
  - One-click document deletion with automatic confirmation.
- **Interactive Chat Workspace**:
  - Live token streaming via Server-Sent Events (SSE).
  - Clean markdown formatting with automated code syntax highlighting.
  - In-line citation pills (e.g. `[1]`, `[2]`).
- **Citation Inspector Drawer**:
  - Click any citation to open a dedicated inspector panel.
  - Displays document filename, page number, relevance score bar, and exact text snippet.
- **Dual Mode Support**:
  - **Live Mode**: Connects directly to your deployed or local FastAPI backend.
  - **Mock Mode**: Fully client-side simulation allowing rapid testing of the interface without needing backend services.

---

## Testing & Quality Assurance

### Backend Unit & Integration Tests
The backend test suite verifies API endpoints, rate limiting, authentication, and Celery tasks:
```bash
cd backend
pytest -v
```

### Frontend Tests & Type Checking
Run the frontend test suite, linter, and type checker:
```bash
cd frontend

# Run unit tests via Vitest
npm run test

# Check code formatting & linting
npm run lint

# Type check
npx tsc --noEmit
```

---

## Production Deployment

### Backend via Docker Compose Production
A production compose configuration is provided in `backend/docker-compose.prod.yml`:
```bash
cd backend
docker compose -f docker-compose.prod.yml up -d --build
```
This configuration:
- Runs Uvicorn with multiple production worker processes.
- Mounts persistent Docker volumes for PostgreSQL data, Redis, and uploads.
- Restricts external port exposure and enables health check recovery policies.

### Cloud Deployment Recommendations
- **Backend API & Celery**: Deploy as a containerized web service and worker service on platforms like Render, AWS ECS, or Fly.io.
- **PostgreSQL**: Managed PostgreSQL with `pgvector` enabled (such as Supabase, Neon, or AWS RDS).
- **Redis**: Managed Redis instance (Upstash, AWS ElastiCache, or Redis Cloud).
- **Frontend**: Deploy the static Vite build output (`frontend/dist`) to Cloudflare Pages, Vercel, or Netlify.

---

## License

This project is licensed under the [MIT License](LICENSE).
