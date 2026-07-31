FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV POETRY_VIRTUALENVS_CREATE=false

RUN pip install --no-cache-dir poetry==2.2.1
WORKDIR /service

COPY apps/mcp/pyproject.toml apps/mcp/poetry.lock ./
RUN poetry install --only main --no-interaction --no-root

COPY apps/mcp/app ./app

EXPOSE 8001
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"]
