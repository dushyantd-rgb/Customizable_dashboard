# Phase 3 coordination

Updated 2026-08-01 by Codex after inspecting Claude session `b3577ea5-b53f-468a-a738-5f9cdb97a9fd`.

## Claude-owned areas

- `apps/api/app/integrations/meta/**`
- `apps/api/app/integrations/google/**`
- `apps/api/app/core/encryption.py`
- `apps/api/app/core/config.py`
- `apps/api/app/api/v1/router.py`
- `apps/api/pyproject.toml`
- Phase 3 database migrations
- Backend integration tests

## Codex-owned areas

- `apps/web/app/clients/[clientId]/integrations/**`
- `apps/web/components/integrations/**`
- Integration-related additions to `apps/web/lib/api-client.ts`
- Integration web tests
- Web lint, tests, typecheck, and build

Claude completed its backend pass and also produced three parallel UI drafts. During integration QA,
Codex found that the drafts targeted table and route names that did not match the Phase 2 schema.
Those original backend, test, documentation, and UI drafts are preserved under
`growthbyte-reporting/.agents/claude-backend-drafts/` and
`growthbyte-reporting/.agents/claude-ui-drafts/`. The live connector files were then aligned to the
actual migrations, client-scoping constraints, and route-wired web panels.

Do not commit `.agents/` or `skills-lock.json`.
