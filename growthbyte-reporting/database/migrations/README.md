# Supabase-compatible migrations

This directory is the ordered source of truth for reporting-database migrations.

## Naming convention

Use UTC timestamps and snake-case descriptions:

```text
YYYYMMDDHHMMSS_description.sql
```

Never edit an applied migration. Add a later migration for every correction. Phase 1 contains an empty transactional baseline. Phase 2 adds the reporting schema in dependency order:

1. `20260801010000_create_client_core.sql`
2. `20260801020000_create_integration_config.sql`
3. `20260801030000_create_sync_and_leads.sql`
4. `20260801040000_create_metrics_reports_audit.sql`

Each Phase 2 file is transaction-wrapped and uses idempotent table, index, extension, function, and trigger operations so the existing lexical runner can safely encounter it again. Applied migrations remain immutable even though re-entry is non-destructive.

The status vocabularies proposed in Phase 0 were not approved. These migrations therefore require non-empty status text without freezing proposed enum values. Add enum or value checks only in a later migration after approval.

## Apply locally

Start a local Supabase/PostgreSQL instance, set `DATABASE_DIRECT_URL` in the current PowerShell session, and run:

```powershell
$env:DATABASE_DIRECT_URL = "postgresql://postgres:postgres@127.0.0.1:54322/postgres"
.\database\apply-migrations.ps1
```

The runner executes files in lexical order with `ON_ERROR_STOP=1` and does not print the connection string. The initial baseline is safe to apply to an empty database and creates no business objects.

`SUPABASE_URL`, `SUPABASE_PUBLISHABLE_KEY`, and `SUPABASE_SECRET_KEY` are API configuration and are not PostgreSQL DDL connection strings. Set `DATABASE_DIRECT_URL` to an explicitly selected empty test database before applying migrations. The knowledge Supabase URL is read-only discovery configuration and is not used by this runner.

## Validate

Run static validation without a database:

```powershell
.\database\validate-migrations.ps1
```

This checks migration order, transaction wrappers, expected tables, UUID keys, non-null client scope, foreign-key creation order, client-leading indexes, and prohibited auth/credential/PII/seed patterns.

When an empty test database and `psql` are available, apply the full migration chain explicitly:

```powershell
$env:DATABASE_DIRECT_URL = "postgresql://postgres:postgres@127.0.0.1:54322/postgres"
.\database\validate-migrations.ps1 -ApplyDatabase
```

Do not point the validation command at a database containing data. No Phase 2 seed data is required or included.
