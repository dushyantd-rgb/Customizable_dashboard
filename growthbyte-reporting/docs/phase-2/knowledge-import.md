# Phase 2 knowledge import

Status: **implemented and unit-tested; local source schema discovered read-only; real import not
run**.

## Scope and architecture

The importer is backend-only Python code in `apps/api`. It has two independently configured
Supabase REST clients:

1. The reporting client can read the reporting `clients` table and atomically upsert
   `client_knowledge` rows.
2. The knowledge client is GET-only. Its allowlist contains `org_clients`,
   `org_knowledge_items`, and `org_knowledge_base_sections`; it has no insert, update, upsert,
   delete, or RPC interface.
3. Repositories accept `client_id` as a mandatory keyword argument. Reporting payloads are
   constructed with that exact target client id rather than copying the source client id.
4. `KnowledgeImportService` performs target validation, source lookup, mapping, preview, and
   confirmed apply orchestration. No import route is exposed because Phase 2 has no application
   authentication. The controlled execution surface is the backend CLI.

Service-role values are Pydantic secrets, excluded from serialization and representation. The
HTTP layer converts transport and backend errors to fixed safe codes. URLs, keys, project
references, response bodies, and raw exception details are not logged or returned.

## Configuration

The implementation reads exactly these backend variables:

- `REPORTING_SUPABASE_URL`
- `REPORTING_SUPABASE_SERVICE_ROLE_KEY`
- `SUPABASE_KNOWLEDGE_BASE_URL`
- `SUPABASE_KNOWLEDGE_BASE_SERVICE_ROLE_KEY`

The two URLs must be HTTP(S) Supabase project URLs suitable for `/rest/v1`, not direct PostgreSQL
connection strings. Placeholders and incomplete pairs are treated as `not_configured`. These
variables must never use a `NEXT_PUBLIC_` prefix.

Local configuration inspection on 2026-08-01 found both required knowledge variable names. The
configured knowledge URL is a direct PostgreSQL URI, so the REST adapter safely treats the source
as not configured. The two required reporting variable names are absent; existing variables under
other names are deliberately not consumed. No `.env` value was copied into code, documentation,
tests, logs, or command output.

## Source schema evidence

Repository evidence in `docs/phase-0/source-schema-inventory.md` identifies:

- `org_clients.id` as the explicit source-client lookup field.
- `org_knowledge_base_sections` with `id`, `client_id`, `section_number`, `section_key`, `title`,
  `content`, `structured_data`, `approvals`, `version`, `created_at`, and `updated_at` among its
  migration-derived columns.
- `org_knowledge_items` with `id`, nullable `client_id`, `title`, `content`, `content_type`, `tags`,
  `created_at`, and `updated_at` among its migration-derived columns.

On 2026-08-01, the already-running local Supabase database labeled for the Phase 0 source project
was queried inside an explicit read-only transaction. `information_schema` confirmed all three
tables and the columns above; additional section completion, gap, review, and change-attribution
columns remain outside the importer allowlist. Aggregate-only counts showed zero rows in each of
the three tables, and the transaction was rolled back. The configured external source host could
not be resolved from disposable Docker, and REST discovery could not use its direct PostgreSQL URL.
No client id, client name, knowledge value, credential, or complete payload was printed or stored.

## Field mapping

| Source                                                          | Reporting target                 | Classification | Rule                                                          |
| --------------------------------------------------------------- | -------------------------------- | -------------- | ------------------------------------------------------------- |
| section `id`                                                    | `source_identifier`              | mapped         | Stable source-row identity                                    |
| section `section_key`                                           | `category`, `knowledge_key`      | mapped         | Stable semantic section key                                   |
| section `title`, `content`, `structured_data`, `section_number` | `value`                          | mapped         | Preserved structured section payload                          |
| section `title`                                                 | `source_display_name`            | mapped         | Display metadata remains separate from identity               |
| section `version`                                               | `source_version`, `version`      | mapped         | No timestamp-derived version is invented                      |
| constant                                                        | `source_type`                    | mapped         | `knowledge_supabase_section`                                  |
| constant                                                        | `source_reference`               | mapped         | Source table name                                             |
| canonical payload SHA-256                                       | `source_hash`                    | mapped         | Deterministic change evidence                                 |
| apply clock and batch UUID                                      | `imported_at`, `import_batch_id` | mapped         | Import metadata generated by reporting backend                |
| explicit target id                                              | `client_id`                      | mapped         | Required and target-validated; source id is never copied      |
| explicit operator value                                         | `status`                         | mapped         | Required for apply; no status is inferred                     |
| section `client_id`                                             | none                             | ignored        | Used only to scope source reads                               |
| section approvals/review attribution and source timestamps      | none                             | ignored        | User/review migration is outside the approved contract        |
| `org_knowledge_items` fields                                    | none                             | unresolved     | Approved subset and stable source-version rule remain blocked |

`org_knowledge_base_section_versions`, documents, comments, and thread status are not queried or
imported. Expanding that allowlist requires an approved mapping and retention contract.

## Preview flow

The preview command requires both source and target identifiers:

```powershell
py -m poetry run python -m app.scripts.knowledge_import preview `
  --source-client-id <source-id> `
  --target-client-id <target-uuid> `
  --target-status <explicit-status>
```

Preview validates the target UUID, confirms the target reporting client exists, requires exactly
one source client, reads the two allowlisted knowledge relations with explicit source-client
filters, maps sections, and returns counts, field classifications, warning codes, and blocker
codes. It contains no write call and its response omits source identifiers and knowledge values.
Omitting `--target-status` is permitted for classification, but returns the
`target_status_required` apply blocker.

## Controlled apply and idempotency

Apply requires the `apply` subcommand, source and target identifiers, an explicit status, and a
second target UUID that must exactly match:

```powershell
py -m poetry run python -m app.scripts.knowledge_import apply `
  --source-client-id <source-id> `
  --target-client-id <target-uuid> `
  --confirm-target-client-id <same-target-uuid> `
  --target-status <explicit-status>
```

Any mapping blocker prevents all reporting writes. A valid plan is sent as one PostgREST upsert
using this exact conflict target:

```text
client_id,source_type,source_identifier,source_version
```

Migration `20260801050000_replace_client_knowledge_source_unique_index.sql` supplies the
non-partial PostgreSQL unique constraint that PostgREST can infer. Repeating an import for the same
target client, source type, source id, and source version updates that identity instead of creating
a duplicate. The repository exposes no delete operation, and the source adapter exposes no write
operation. A conflict or unexpected response count fails safely; no compensating delete occurs.

No real apply command was run while implementing or validating this layer.

## Readiness and failure handling

`/ready` reports only `configured`, `reachable`, `unavailable`, or `not_configured` for each
Supabase dependency and its overall status. The overall state is `reachable` only when both
dependencies are reachable. The response contains no endpoint, credential, project reference, or
raw error.

Fixed errors cover invalid target UUID, invalid source identifier, missing target client, missing
source client, duplicate source client, missing section fields, unavailable source/reporting
databases, mapping blockers, confirmation mismatch, PostgREST upsert conflict, and partial response.

## Validation

Mocked tests cover mandatory target-client filtering, GET-only source access, source filtering,
preview zero-write behavior, mapping classification, missing/duplicate clients, invalid ids,
missing fields, explicit confirmation, repeated idempotent apply, absence of deletes, the exact
four-column PostgREST conflict target, safe readiness, placeholder handling, unavailable databases,
upsert conflicts, and secret-safe errors. Fixtures contain only short synthetic fragments.

Disposable PostgreSQL 17 validates all six migrations, the source-identity constraint, four-column
`ON CONFLICT` inference, and PostgreSQL null behavior. The labeled container was removed afterward.
A disposable reporting PostgREST stack was not installed, so reporting REST integration was
mocked. Live read-only preview validation was skipped because the configured knowledge URL is not
HTTP(S) and the verified local source tables are empty. These checks must be rerun after correct
HTTP(S) project URLs and de-identified source evidence are configured. Production was not contacted
or modified.

## Blockers

1. Configure the two required reporting variables under their exact names.
2. Replace the knowledge direct PostgreSQL URI with the source Supabase HTTP(S) project URL for
   REST discovery and preview.
3. Approve the `org_knowledge_items` subset, taxonomy, status vocabulary, source-version rule, and
   any history/document/review mapping before expanding the importer.
4. Add authentication/authorization before exposing import behavior over an API or public network.
