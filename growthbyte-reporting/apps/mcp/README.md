# MCP service

Python MCP SDK and FastAPI foundation using Streamable HTTP.

Phase 1 provides `/health`, `/ready`, a transport mount at `/mcp`, and an intentionally empty tool-registration function. No reporting tools, database access, integrations, or GLM calls are included.

Run from this directory with `poetry run uvicorn app.main:app --reload --port 8001`.
