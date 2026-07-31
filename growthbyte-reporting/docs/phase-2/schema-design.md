# Phase 2 database schema design

Status: **structural schema implemented; contract-dependent values and live database application remain blocked**.

## Scope and evidence

This design implements only the Phase 2 database foundation requested for the standalone reporting project. It was reconciled against the repository TRD, every Phase 0 document, the Phase 1 foundation summary, and the existing migration runner and migration README.

`PROJECT_HANDOFF.md` is not present in the repository or project directory, so it could not be reviewed. Phase 0 also marks the canonical schema, status mappings, metric semantics, lead attribution details, and knowledge migration scope as proposed or blocked rather than approved. The migrations therefore establish relational boundaries and lineage without inventing those unresolved business values.

No API endpoint, Supabase application client, knowledge importer, OAuth flow, UI, agent, MCP feature, RLS user policy, authentication table, or seed data is included.

## Migration order

| Migration                                         | Objects introduced                                                                                  |
| ------------------------------------------------- | --------------------------------------------------------------------------------------------------- |
| `20260801000000_empty_baseline.sql`               | Phase 1 no-op baseline                                                                              |
| `20260801010000_create_client_core.sql`           | `pgcrypto`, updated-time trigger function, `clients`, `client_knowledge`, `client_kpis`             |
| `20260801020000_create_integration_config.sql`    | `integration_connections`, `google_sheet_configs`, `field_mappings`, `status_mappings`              |
| `20260801030000_create_sync_and_leads.sql`        | `sync_runs`, `raw_sheet_rows`, `lead_records`, `lead_matches`                                       |
| `20260801040000_create_metrics_reports_audit.sql` | `metric_snapshots`, `reports`, `report_versions`, `report_version_metric_snapshots`, `audit_events` |

The requested 15 logical tables are present. `report_version_metric_snapshots` is a supporting association table that normalizes the canonical report version's metric-snapshot array into enforceable same-client foreign keys.

## Client separation and identifiers

`clients.id` is the tenant root and is therefore the one deliberate exception to carrying a separate `client_id`. Every other table is client-owned and has a non-null `client_id` referencing `clients(id)`.

Every parent referenced by another client-owned row exposes `unique (client_id, id)`. Child relationships use composite foreign keys such as `(client_id, report_id)` and `(client_id, metric_snapshot_id)`. This prevents a row from linking to another client's parent even when an application supplies conflicting UUIDs.

Internal identities use PostgreSQL UUID primary keys with `gen_random_uuid()`. Provider and source identifiers remain text because Meta and Google identifiers are external opaque values. Stable source identifiers and mutable display names are stored in separate columns on integration connections, knowledge sources, lead matches, and metric entity scope.

## Logical table groups

### Client configuration

- `clients` stores the reporting name, slug, timezone, currency, and lifecycle text.
- `client_knowledge` stores versioned JSON knowledge plus source type, source identifier/display name/reference, source version/hash, import batch, and import time. It contains no source credentials or signed connection details.
- `client_kpis` stores effective-dated metric configuration. The unrequested `client_goals` table and its `goal_id` relationship are not invented.

### Integrations and Sheet mappings

- `integration_connections` contains only non-secret provider/account metadata. It deliberately has no token, secret, key, password, ciphertext, or credential payload column.
- `google_sheet_configs` stores a spreadsheet ID separately from its worksheet display name and may link to a same-client connection.
- `field_mappings` and `status_mappings` are versioned per Sheet configuration. Transform values are declarative JSON, not executable code.

### Sync and lead evidence

- `sync_runs` records source/configuration lineage, time windows, row reconciliation counts, and redacted error summaries.
- `raw_sheet_rows` preserves versioned source evidence and hashes for one client, configuration, and sync run.
- `lead_records` stores normalized source/Meta identifiers and outcome timing. Direct name, phone, and email columns are intentionally absent because Phase 0 did not approve encryption/tokenization and retention decisions.
- `lead_matches` records one active attribution decision per lead while retaining prior inactive decisions. External account/campaign/ad-set/ad identifiers are separate from display names.

### Metrics, reports, and operations

- `metric_snapshots` stores immutable calculation inputs, components, formula version, cutoff, quality status/reasons, and external entity identity/display metadata.
- `reports` is the logical report root; `report_versions` stores schema-versioned content and hashes.
- `report_version_metric_snapshots` gives every report input an enforceable same-client foreign key.
- `audit_events` is append-only by design and uses a process identifier plus optional operator label, not an application user identity. Its polymorphic `entity_id` cannot have one target foreign key; `client_id`, optional `sync_run_id`, action, entity type, and time remain indexed.

## Constraints and indexes

- UUID primary keys on all logical entities; a UUID composite primary key on the report/snapshot association.
- Unique client-scoped source identities for knowledge versions, integration source accounts, Sheet tabs, mapping versions, raw rows per sync, and report versions.
- A partial unique index permits only one active `lead_matches` row per client/lead.
- An expression-based unique index prevents duplicate metric snapshots with identical client, metric, period, attribution scope, entity, formula version, and input cutoff.
- Client-leading lookup indexes cover every client-owned table, with period/status/source indexes for expected ingestion and reporting access paths.
- Interval, positive version/count, currency format, JSON shape, and review timestamp/label coherence checks are included where the contract supports them.
- Mutable configuration and workflow tables use a shared `updated_at` trigger. Immutable metric snapshots and append-only audit/association rows use creation or event timestamps without update triggers.

## Status handling

No Phase 0 status vocabulary is approved. In particular, the six lead statuses, sync states, connection states, report states, metric quality states, and client/knowledge states are all still proposed. The schema records non-empty text but does not add enum types or `status in (...)` constraints. A later approved migration must freeze allowed values and transition rules before ingestion or report generation starts.

## Credentials and environment integration

The local `.env` was inspected by key name and set/empty state only; no value was printed or copied. It contains the reporting Supabase URL, publishable key, secret key, JWKS URL, and knowledge-base URL. `.env.example` now documents those names with placeholders.

The schema does not consume Supabase API keys. PostgreSQL DDL requires `DATABASE_DIRECT_URL`, which is not present in the local `.env`. The Supabase knowledge URL is documented as read-only discovery configuration only; there is no knowledge runtime connection, query, import, copy, or write in Phase 2. Credentials remain local/backend-only and outside every business table.

## Validation and blockers

`database/validate-migrations.ps1` validates lexical order, transaction wrappers, table presence, UUID keys, non-null client scope, foreign-key creation order, client-leading indexes, and forbidden auth/credential/PII/seed patterns. With an explicitly supplied empty test database and `psql`, the same command can invoke the existing migration runner using `-ApplyDatabase`.

Current blockers are:

1. `PROJECT_HANDOFF.md` is missing, so any additional handoff decisions cannot be verified.
2. `DATABASE_DIRECT_URL`, `psql`, and the Supabase CLI are unavailable locally, so empty-database application and server-side PostgreSQL syntax validation cannot yet run.
3. The knowledge source selection, field scope, provenance acceptance, PII/retention rules, and import validation remain unapproved. No knowledge data is copied.
4. Pilot Sheet samples, canonical field allowlist, status mappings, duplicate/funnel rules, and attribution evidence remain unapproved. No proposed enum or contact-data storage is frozen.
5. KPI unit/direction/attribution catalogs and metric/report workflow/quality statuses remain unapproved. They remain non-empty text until a later migration records approved values.
6. Meta dimension tables are outside the requested list, so `lead_matches` and `metric_snapshots` keep provider-scoped external identifiers rather than inventing foreign keys to missing entities.

These blockers prevent declaring the schema contract fully approved or applying it to the new database, but they do not require application, integration, or Phase 3 work in this task.
