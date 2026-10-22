#!/bin/sh
set -e

echo "==> Running Alembic database migrations..."
alembic upgrade head

echo "==> Starting Celery background worker..."
celery -A app.worker.celery_app worker --loglevel=info -c 1 &

echo "==> Starting Uvicorn FastAPI server on port ${PORT:-10000}..."
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-10000}"
