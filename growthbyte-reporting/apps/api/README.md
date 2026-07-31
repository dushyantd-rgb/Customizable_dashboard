# API service

FastAPI foundation for backend-only reporting operations.

Phase 1 provides `/health`, `/ready`, and `/api/v1/health`, plus settings, CORS, structured logging, and safe global error handling. It does not create integrations, database clients, or reporting-domain routes.

Run from this directory with `poetry run uvicorn app.main:app --reload --port 8000`.
