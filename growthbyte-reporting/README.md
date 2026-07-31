# GrowthByte Reporting Platform

GrowthByte Reporting is a standalone platform foundation for combining verified marketing data and human-reviewed lead outcomes in later delivery phases. Phase 1 establishes the repository and service boundaries only; it does not connect to external systems or implement reporting features.

## Phase 1 boundary

- No application login, authentication, authorization, users, memberships, roles, or permission matrix.
- Local or trusted-private-network use only. Do not expose these services publicly.
- No Supabase business tables, RLS user policies, client knowledge migration, Meta or Google integration, ingestion, metrics, agent calls, reporting tools, dashboards, or PDF generation.
- All external credentials remain backend-only placeholders and are unused by the Phase 1 services.
- Google OAuth is reserved solely for a later Google Sheets connection.

The Phase 1 brief's confirmed MVP rules supersede the older authentication and RLS assumptions in the draft TRD.

## Architecture

| Component        | Technology                                     | Phase 1 responsibility                                                      |
| ---------------- | ---------------------------------------------- | --------------------------------------------------------------------------- |
| `apps/web`       | Next.js 15, React 18, TypeScript, Tailwind CSS | Application shell, `/health`, API status display                            |
| `apps/api`       | Python 3.11, FastAPI, Pydantic, Poetry         | `/health`, `/ready`, `/api/v1` router foundation, CORS, safe logging/errors |
| `apps/mcp`       | Python 3.11, MCP SDK, FastAPI, Poetry          | `/health`, `/ready`, empty Streamable HTTP transport at `/mcp`              |
| `packages/*`     | TypeScript                                     | UI, health types, report-schema placeholder, browser-safe configuration     |
| `database`       | Supabase-compatible PostgreSQL migrations      | Empty ordered baseline and local runner                                     |
| `infrastructure` | Docker and GitHub Actions                      | Local containers and validation-only CI                                     |

## Project structure

```text
customizable dashboard/              # Git repository root
  .github/workflows/ci.yml           # GitHub-discovered validation workflow
  growthbyte-reporting/              # Project and command root
    apps/
      web/
      api/
      mcp/
    packages/
      ui/
      shared-types/
      report-schema/
      config/
    database/
      migrations/
      policies/
      seed/
    infrastructure/
      docker/
      helm/
      github-actions/
    docs/
      phase-0/
      phase-1/
    docker-compose.yml
    package.json
    pnpm-workspace.yaml
    turbo.json
```

## Prerequisites

- Node.js 22 LTS and pnpm 10
- Python 3.11 and Poetry 2.2.1
- Docker Desktop with Compose, when using containers
- PostgreSQL `psql`, only when applying the empty baseline migration manually

The repository records Node 22 in `.nvmrc` and Python 3.11 in `.python-version`. CI and Docker use those versions.

## Windows PowerShell setup

```powershell
Set-Location "D:\growthbyte\customizable dashboard\growthbyte-reporting"
corepack enable
corepack prepare pnpm@10.31.0 --activate
pnpm install

Push-Location apps/api
poetry install --no-root
Pop-Location

Push-Location apps/mcp
poetry install --no-root
Pop-Location

Copy-Item .env.example .env
```

Phase 1 starts with the placeholder values unchanged because no external connection is initialized or validated.

## Local development

Run all services through Turborepo:

```powershell
pnpm dev
```

Or run them in separate terminals:

```powershell
pnpm --filter @growthbyte/web dev
```

```powershell
Set-Location apps/api
poetry run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

```powershell
Set-Location apps/mcp
poetry run uvicorn app.main:app --reload --host 0.0.0.0 --port 8001
```

Health endpoints:

- Web: `http://localhost:3000/health`
- API: `http://localhost:8000/health`, `http://localhost:8000/ready`, `http://localhost:8000/api/v1/health`
- MCP: `http://localhost:8001/health`, `http://localhost:8001/ready`
- MCP Streamable HTTP mount: `http://localhost:8001/mcp`

## Docker development

No external secret is required by the containers in Phase 1.

```powershell
docker compose up --build
docker compose ps
docker compose down
```

Compose reads matching non-secret values from a root `.env` when present and otherwise uses safe local defaults.

## Quality and tests

Run the complete workspace checks after Node and Python dependencies are installed:

```powershell
pnpm format:check
pnpm lint
pnpm test
pnpm typecheck
pnpm build
```

Individual Python checks can also be run from each service directory:

```powershell
poetry run ruff format --check .
poetry run ruff check .
poetry run pytest
```

## Migration foundation

Migration files use `YYYYMMDDHHMMSS_description.sql` names under `database/migrations`. To apply them to a local empty Supabase/PostgreSQL database:

```powershell
$env:DATABASE_DIRECT_URL = "postgresql://postgres:postgres@127.0.0.1:54322/postgres"
.\database\apply-migrations.ps1
```

The Phase 1 baseline creates no schema objects or business tables.

## Current status and evidence blockers

Phase 1 foundation implementation is documented in `docs/phase-1/foundation-summary.md`.

The latest TRD is now present. Phase 0 evidence remains unresolved for two named pilot Sheets, pilot Meta fields/permissions, lead-status and funnel definitions, and the knowledge migration strategy. Those blockers do not cause Phase 1 to invent contracts; they remain gates for later business-domain implementation.
