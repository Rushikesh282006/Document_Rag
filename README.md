# Multi-Tenant Document RAG Platform

This repository is organized into a clean decoupled architecture:

```text
Document_Rag/
├── backend/                  # FastAPI, PostgreSQL (pgvector), Celery, Redis, LangChain
│   ├── app/                  # Application source code
│   ├── migrations/           # Alembic database migrations
│   ├── tests/                # Test suite
│   ├── uploads/              # Local PDF storage
│   ├── .env                  # Environment variables & API keys
│   ├── docker-compose.yml    # Database, Redis, API, and Worker orchestration
│   ├── Dockerfile            # Container definition
│   └── requirements.txt      # Python dependencies
│
└── frontend/                 # User Interface (Web Client)
```

## Getting Started

### 1. Start Backend Services
Navigate to the `backend/` directory:
```bash
cd backend
docker compose up -d
```
API Documentation will be available at: [http://localhost:8000/api/v1/docs](http://localhost:8000/api/v1/docs)

### 2. Frontend
Clone or initialize your frontend repository into the `frontend/` folder.
