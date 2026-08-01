# GrowthByte Reporting Platform

GrowthByte Reporting is a standalone platform for combining verified marketing data and
human-reviewed lead outcomes. Phase 2 now includes the reporting database schema, a controlled
knowledge-import layer, and internal client knowledge and KPI management. Connectors, ingestion,
metric calculation, report generation, and production deployment remain later-phase work.

## Current trusted-internal boundary

- No application login, authentication, authorization, users, memberships, roles, or permission matrix.
- Local or trusted-private-network use only. Do not expose these services publicly.
- Reporting Supabase is the primary application database. Every client-owned application query
  requires explicit `client_id` filtering, which provides logical separation rather than an
  authorization boundary.
- Knowledge Supabase is a strictly read-only source for controlled preview/import. It must never
  receive inserts, updates, upserts, deletes, or mutating RPC calls.
- There are no user-based RLS policies, Meta or Google connectors, ingestion jobs, metric
  calculations, agent calls, reporting tools, dashboards, or PDF generation yet.
- Service-role credentials remain backend-only and must never enter browser bundles, API responses,
  logs, errors, fixtures, or snapshots.

The confirmed trusted-internal MVP rules supersede the older authentication and RLS assumptions in
the draft TRD.

## Architecture

| Component        | Technology                                     | Current responsibility                                                                           |
| ---------------- | ---------------------------------------------- | ------------------------------------------------------------------------------------------------ |
| `apps/web`       | Next.js 15, React 18, TypeScript, Tailwind CSS | Health view plus internal client, knowledge, and KPI management routes                           |
| `apps/api`       | Python 3.11, FastAPI, Pydantic, Poetry         | Safe health/readiness, reporting repositories, client/knowledge/KPI API, controlled importer CLI |
| `apps/mcp`       | Python 3.11, MCP SDK, FastAPI, Poetry          | `/health`, `/ready`, empty Streamable HTTP transport at `/mcp`                                   |
| `packages/*`     | TypeScript                                     | Shared API contracts, UI primitives, report-schema placeholder, browser-safe configuration       |
| `database`       | Supabase-compatible PostgreSQL migrations      | Ordered Phase 2 reporting schema, validation, and local runner                                   |
| `infrastructure` | Docker and GitHub Actions                      | Local containers and validation-only CI                                                          |

## Project structure

```text
growthbyte-reporting/
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
    phase-2/
  .github/workflows/ci.yml
  docker-compose.yml
  package.json
  pnpm-workspace.yaml
  turbo.json
```

## Prerequisites

- Node.js 22 LTS and pnpm 10
- Python 3.11 and Poetry 2.2.1
- Docker Desktop with Compose, when using containers
- PostgreSQL `psql`, when applying migrations manually

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

Leave placeholders unchanged when database connectivity is not needed. Backend database access
uses these exact environment variable names:

- `REPORTING_SUPABASE_URL`
- `REPORTING_SUPABASE_SERVICE_ROLE_KEY`
- `SUPABASE_KNOWLEDGE_BASE_URL`
- `SUPABASE_KNOWLEDGE_BASE_SERVICE_ROLE_KEY`

The URLs must be HTTP(S) Supabase project URLs for the REST clients. Never prefix a service-role
variable with `NEXT_PUBLIC_`.

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

Internal application routes:

- Web: `/clients`, `/clients/[clientId]`, `/clients/[clientId]/knowledge`
- API: `/api/v1/clients`
- API: `/api/v1/clients/{client_id}/knowledge`
- API: `/api/v1/clients/{client_id}/kpis`

The nested knowledge and KPI APIs support list/get/create/update only. There are no delete or
generic table-access endpoints.

## Docker development

Health-only local containers can start without external secrets. Database-backed management
behavior reports safe `not_configured` readiness states until its backend variables are configured.

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

## Database migrations

Migration files use `YYYYMMDDHHMMSS_description.sql` names under `database/migrations`. To apply them to a local empty Supabase/PostgreSQL database:

```powershell
$env:DATABASE_DIRECT_URL = "postgresql://postgres:postgres@127.0.0.1:54322/postgres"
.\database\apply-migrations.ps1
```

The ordered migrations create the Phase 2 client, knowledge, KPI, integration-configuration, sync,
lead, metric, report, and audit structures. `database/validate-migrations.ps1` validates migration
order, transaction wrappers, UUID identities, non-null client scope, same-client foreign-key order,
client-leading indexes, the knowledge-import conflict target, and secret/PII guards.

## Current status and evidence blockers

Phase 1 foundation implementation is documented in `docs/phase-1/foundation-summary.md`. Phase 2
schema, controlled knowledge import, and client knowledge/KPI management are documented in:

- `docs/phase-2/schema-design.md`
- `docs/phase-2/knowledge-import.md`
- `docs/phase-2/client-knowledge-and-kpi.md`

No live pilot can be claimed: the discovered knowledge-source tables are empty and no approved pilot
client identifiers were supplied. No real client has been imported. The original Phase 2 TRD exit
criteria around assigned users and cross-client RLS also remain unmet because authentication and
RLS are explicitly outside this trusted MVP. KPI semantic catalogs, the free-form knowledge-item
mapping, pilot Sheets, lead-status/funnel rules, and attribution evidence remain unresolved Phase 0
contracts. Live REST checks also remain blocked until the reporting configuration uses the exact
backend names above and the knowledge URL is an HTTP(S) Supabase project URL. Phase 3 has not
started.
