# GrowthByte Reporting project handoff

Status: Phase 1 repository foundation with sign-off cleanup in progress on `chore/phase-1-signoff-fixes`.

## Repository facts

- Git repository root: `D:\growthbyte\customizable dashboard`
- Project directory: `D:\growthbyte\customizable dashboard\growthbyte-reporting`
- Baseline commit at cleanup start: `ebef50d` (`Initial commit`)
- GitHub Actions workflow: repository-root `.github/workflows/ci.yml`
- Application version: `0.1.0`
- Package manager: pnpm `10.31.0`
- Declared runtimes: Node.js 22 and Python 3.11

Run project commands from `growthbyte-reporting/`, not from the Git repository root, unless a command explicitly supplies that path.

## Phase 1 scope

Phase 1 contains repository and platform foundation only:

- Next.js web shell with `/` and `/health`
- FastAPI service with `/health`, `/ready`, and `/api/v1/health`
- Python MCP service with `/health`, `/ready`, and Streamable HTTP at `/mcp`
- Shared TypeScript package foundations
- Empty transactional migration baseline and migration runner
- Docker development definitions and validation-only CI

It does not contain application authentication, business-domain database tables, data migration, external integrations, ingestion, matching, metrics, reporting tools, dashboards, agent calls, PDF generation, deployment, or Phase 2 work.

## Local setup and validation

From the project directory:

```powershell
pnpm install --frozen-lockfile

Push-Location apps/api
poetry install --no-root
Pop-Location

Push-Location apps/mcp
poetry install --no-root
Pop-Location

pnpm format:check
pnpm lint
pnpm test
pnpm typecheck
pnpm build
docker compose config --quiet
```

The API and MCP projects retain their own `pyproject.toml` and `poetry.lock` files. The repository-root workflow runs Poetry commands from `growthbyte-reporting/apps/api` and `growthbyte-reporting/apps/mcp` respectively.

## Environment boundary

`.env.example` contains placeholders only for:

- application and local service URLs;
- reporting Supabase;
- existing knowledge Supabase read-only inspection;
- Google Sheets OAuth;
- Meta access;
- the GLM gateway; and
- MCP transport settings.

The knowledge Supabase is not a Phase 1 runtime dependency and must not be written to or copied. Real credentials belong only in an untracked `.env` or an approved secret store.

## CI behavior

The repository-root workflow has three jobs:

1. Frontend and shared-package formatting, linting, test, typecheck, build, and Compose validation.
2. API dependency installation, Ruff formatting/linting, and Pytest on Python 3.11.
3. MCP dependency installation, Ruff formatting/linting, and Pytest on Python 3.11.

It contains no deployment or external-integration job.

## Known evidence and environment limits

- Pilot Sheet and Meta evidence, lead-status decisions, and the knowledge migration strategy remain unresolved Phase 0 inputs for later business work.
- The Phase 1 baseline migration contains no DDL or DML.
- The previous local verification could not build Docker images because the Docker engine was not running.
- The previous local verification could not apply the baseline to a live database because neither `psql` nor Supabase CLI was installed.

## Next operator action

Review the sign-off cleanup diff and local validation output. Commit and push the branch only after explicit approval. Do not begin Phase 2 automatically.
