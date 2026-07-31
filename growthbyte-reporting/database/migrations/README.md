# Supabase-compatible migrations

This directory is the ordered source of truth for reporting-database migrations.

## Naming convention

Use UTC timestamps and snake-case descriptions:

```text
YYYYMMDDHHMMSS_description.sql
```

Never edit an applied migration. Add a later migration for every correction. Phase 1 contains only an empty transactional baseline; business-domain tables begin only after their contracts are approved in a later phase.

## Apply locally

Start a local Supabase/PostgreSQL instance, set `DATABASE_DIRECT_URL` in the current PowerShell session, and run:

```powershell
$env:DATABASE_DIRECT_URL = "postgresql://postgres:postgres@127.0.0.1:54322/postgres"
.\database\apply-migrations.ps1
```

The runner executes files in lexical order with `ON_ERROR_STOP=1` and does not print the connection string. The initial baseline is safe to apply to an empty database and creates no business objects.
