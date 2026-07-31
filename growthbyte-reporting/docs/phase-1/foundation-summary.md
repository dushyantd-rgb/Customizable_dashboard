# Phase 1 foundation summary

Date: 1 August 2026  
Scope: Repository and Platform Foundation only

## Outcome

The repository now contains a Turborepo/pnpm monorepo foundation, three independently runnable services, four minimal shared TypeScript packages, an empty database migration baseline, development containers, tests, lint/format configuration, and validation-only GitHub Actions.

Final command and health-check evidence is recorded below after local verification.

## Material technical decisions

1. **Phase-specific scope wins over draft TRD conflicts.** The Phase 1 brief's confirmed MVP boundary removes application authentication, authorization, users, memberships, roles, permission matrices, and RLS user authorization. No Phase 2 identity model was scaffolded.
2. **Runtime versions are explicit.** Node 22 LTS and pnpm 10 are the JavaScript baseline. Python 3.11 is the deployment and CI baseline; package constraints also permit newer compatible local interpreters below 3.14 so foundation checks can run without changing production intent.
3. **Workspace tasks are orchestrated by Turborepo.** `dev`, `build`, `lint`, `format`, `test`, and `typecheck` run from the root. Lightweight package manifests let Turbo orchestrate Poetry services alongside TypeScript packages without merging their dependency managers.
4. **Frontend dependencies stay on the approved major versions.** The web uses Next.js 15, React 18, TypeScript, Tailwind CSS, ESLint, Jest, and jsdom. Styling is limited to the approved teal, amber, black, and white palette with no gradients.
5. **Shared packages expose source during foundation development.** Each package is private, TypeScript-checkable, and imported through pnpm workspace aliases. This avoids premature publication/build contracts while keeping package boundaries compilable.
6. **API health is independent of external systems.** FastAPI settings have safe defaults, read the optional root `.env`, ignore unrelated placeholders, and do not validate or connect to external credentials. CORS accepts only `WEB_URL`. JSON logs and the global error handler avoid serializing settings, request bodies, or exception details in responses.
7. **The MCP server is transport-only.** The Python MCP SDK provides a stateless Streamable HTTP mount. Tool registration is an explicit empty function; no reporting tool, database access, client query, integration, or GLM call exists.
8. **The environment template was reduced to the confirmed inventory.** JWT, application auth secrets, RLS user configuration, MCP auth tokens, AWS configuration, internal job tokens, and extra encryption keys were removed. Browser-exposed variables contain only public service URLs.
9. **Database setup is deliberately empty.** The ordered SQL baseline is a transaction containing no extensions, schemas, tables, policies, functions, or data. A PowerShell runner applies migrations lexically with PostgreSQL `ON_ERROR_STOP` without printing the database URL.
10. **Containers do not embed secrets.** Compose injects only non-secret service settings and local URLs. Dockerfiles install from lockfiles and use Node 22 or Python 3.11.
11. **CI validates but does not deploy.** GitHub Actions installs frozen pnpm dependencies, Python 3.11, and Poetry, then runs frontend lint/test/typecheck/build plus Ruff/Pytest for each Python service and validates Compose syntax. There are no cloud, deployment, Helm release, or integration jobs.
12. **Phase 0 evidence is preserved.** Files under `docs/phase-0` are excluded from automated formatting and were not modified during Phase 1.

## Services

| Service | Port | Foundation endpoints                              |
| ------- | ---: | ------------------------------------------------- |
| Web     | 3000 | `/`, `/health`                                    |
| API     | 8000 | `/health`, `/ready`, `/api/v1/health`             |
| MCP     | 8001 | `/health`, `/ready`, `/mcp` Streamable HTTP mount |

## Verification evidence

Dependencies were installed and locked with pnpm 10.31.0 and Poetry 2.2.1. The resolved foundation includes Next.js 15.5.22, React 18.3.1, FastAPI 0.116.2, and Python MCP SDK 1.29.0.

| Check                           | Result                                                                                 |
| ------------------------------- | -------------------------------------------------------------------------------------- |
| `pnpm format:check`             | Passed: Prettier plus Ruff format checks for both Python services                      |
| `pnpm lint`                     | Passed: seven workspace packages; ESLint and Ruff reported no errors                   |
| `pnpm test`                     | Passed: one web smoke test, one API health test, and one MCP health/transport test     |
| `pnpm typecheck`                | Passed: all TypeScript packages plus both Poetry lock checks                           |
| `pnpm build`                    | Passed: seven workspace packages; Next.js generated `/` and `/health` as static routes |
| `docker compose config --quiet` | Passed                                                                                 |
| Migration static validation     | Passed: runner parses, baseline is transactional, and it contains no DDL or DML        |
| Secret-pattern scan             | Passed: no credential-shaped values or forbidden active configuration keys found       |
| Phase 0 preservation            | Passed: all ten `docs/phase-0/*.md` files remain present and excluded from formatting  |

Local tests ran with the available Python 3.13.5 interpreter. Python 3.11 remains the declared, CI, and Docker runtime and is enforced by those environments.

### Live service checks

All services were started together without an `.env` file or external connection. Temporary processes were stopped after verification.

| Endpoint              | Result                                                               |
| --------------------- | -------------------------------------------------------------------- |
| Web `/health`         | HTTP 200; expected application health content rendered               |
| API `/health`         | HTTP 200; `status=ok`, version `0.1.0`                               |
| API `/ready`          | HTTP 200; `status=ready`                                             |
| API `/api/v1/health`  | HTTP 200; `status=ok`                                                |
| MCP `/health`         | HTTP 200; `status=ok`, version `0.1.0`                               |
| MCP `/ready`          | HTTP 200; `status=ready`                                             |
| MCP `/mcp` initialize | HTTP 200; SDK initialization response returned and declared no tools |

### Environment-only verification warnings

- Docker Compose syntax passed, but image builds were not run because the local Docker engine was not running.
- Neither `psql` nor the Supabase CLI is installed, so the empty migration was not executed against a live local database. The PowerShell runner and SQL baseline were statically validated; the baseline contains only `BEGIN` and `COMMIT`.
- The local Git directory triggers a dubious-ownership warning between the sandbox's Windows identities. Read-only status commands use a process-scoped safe-directory option; no global Git configuration was changed.

## Known evidence blockers

- Two pilot clients and de-identified Sheet samples are not supplied.
- Pilot Meta field, action, permission, and attribution availability is not verified.
- Lead-status, reviewed-lead, duplicate, and converted/qualified rules are not approved.
- The client-knowledge migration scope and validation strategy are unresolved.

These items intentionally remain documentation blockers only; Phase 1 added no inferred business fields or later-phase implementation.
