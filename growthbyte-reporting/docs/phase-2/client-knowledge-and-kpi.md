# Phase 2 client knowledge and KPI management

Status: **implemented for the trusted internal MVP; live pilot validation and the original
authentication/RLS exit criteria remain blocked**.

## Scope and architecture

This layer manages reporting clients, client-scoped reporting knowledge, and effective-dated KPI
configuration. Reporting Supabase is the application database. The separate knowledge Supabase is
used only by the controlled, read-only import adapter documented in `knowledge-import.md`.

The MVP intentionally has no login, authentication, membership, role, or user table. It also has
no user-based RLS policy. The API uses a reporting service role on the backend, so mandatory
application-level `client_id` filters provide logical separation for trusted internal use; they are
not an authorization or security boundary.

No connector, lead-ingestion, metric-calculation, report-generation, MCP, GLM, or Phase 3 behavior
is part of this layer.

## Phase 2 completion matrix

| Requirement                                        | Status                                | Repository evidence and limitation                                                                                                                                                                                                                                                                           |
| -------------------------------------------------- | ------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Client, knowledge, and KPI tables                  | Complete                              | `clients`, `client_knowledge`, and `client_kpis` are created by `20260801010000_create_client_core.sql`.                                                                                                                                                                                                     |
| Integration, sync, lead, metric, and report tables | Complete structurally                 | The ordered Phase 2 migrations create integration metadata and mappings, sync evidence, lead records/matches, metric snapshots, versioned reports, their snapshot association, and audit events. Connector and calculation behavior remains later-phase work.                                                |
| Constraints and indexes                            | Partial                               | UUID identities, same-client composite foreign keys, uniqueness, interval/shape checks, and client-leading indexes are implemented and migration-validated. Approved status, KPI unit, direction, attribution, metric, and report-state catalogs remain unavailable and therefore are not invented as enums. |
| Audit fields                                       | Complete for the no-auth architecture | Mutable records use `created_at` and `updated_at`; knowledge carries import/approval provenance; operational `audit_events` carry process/operator labels and event time. No user foreign key is created.                                                                                                    |
| Logical `client_id` scoping                        | Complete for this trusted MVP         | Every client-owned table has non-null `client_id`; owned repository calls require it; record reads and updates filter by both `client_id` and record id. This does not replace authorization or RLS.                                                                                                         |
| Knowledge import layer                             | Complete; live validation blocked     | Preview, explicit apply confirmation, read-only source access, and atomic four-column idempotent upsert are implemented. Source tables are empty locally and no real import has been run.                                                                                                                    |
| Client knowledge API                               | Complete                              | Client-scoped list/get/create/update routes are available. There is no delete route.                                                                                                                                                                                                                         |
| KPI API                                            | Complete                              | Client-scoped list/get/create/update routes use only current schema fields. There is no calculation or delete route.                                                                                                                                                                                         |
| Client knowledge UI                                | Complete                              | Client navigation and a grouped knowledge management screen distinguish manual and imported records and provide create/edit flows without deletion.                                                                                                                                                          |
| KPI UI                                             | Complete                              | The client detail screen provides effective-dated KPI list/create/edit behavior without calculating performance.                                                                                                                                                                                             |
| Two de-identified development clients              | Complete for automated fixtures       | Test-only clients use different synthetic knowledge and KPI structures and are never applied as database seeds.                                                                                                                                                                                              |
| Two live pilot knowledge records                   | Blocked                               | No approved pilot identifiers or populated source records are available. Fixture coverage is not live-pilot validation.                                                                                                                                                                                      |
| Client-isolation tests                             | Complete for logical scoping          | Automated tests prove client-filtered knowledge and KPI access, scoped record lookup/update, request-body immutability, and safe unknown-client behavior. Cross-client RLS cannot be claimed because RLS/authentication is deliberately absent.                                                              |

## API routes

All management endpoints are nested under `/api/v1`:

| Method  | Route                                                  | Behavior                                                                |
| ------- | ------------------------------------------------------ | ----------------------------------------------------------------------- |
| `GET`   | `/api/v1/clients`                                      | List reporting-client summaries.                                        |
| `GET`   | `/api/v1/clients/{client_id}`                          | Return reporting-client details or a safe `404`.                        |
| `GET`   | `/api/v1/clients/{client_id}/knowledge`                | List knowledge belonging to the target client.                          |
| `GET`   | `/api/v1/clients/{client_id}/knowledge/{knowledge_id}` | Retrieve one record only when both identifiers match.                   |
| `POST`  | `/api/v1/clients/{client_id}/knowledge`                | Create a manually maintained reporting-knowledge record.                |
| `PATCH` | `/api/v1/clients/{client_id}/knowledge/{knowledge_id}` | Update editable knowledge fields without changing client or provenance. |
| `GET`   | `/api/v1/clients/{client_id}/kpis`                     | List KPI definitions belonging to the target client.                    |
| `GET`   | `/api/v1/clients/{client_id}/kpis/{kpi_id}`            | Retrieve one KPI only when both identifiers match.                      |
| `POST`  | `/api/v1/clients/{client_id}/kpis`                     | Create an effective-dated KPI definition.                               |
| `PATCH` | `/api/v1/clients/{client_id}/kpis/{kpi_id}`            | Update an existing same-client KPI definition.                          |

There are no generic table-access, delete, import, credential, or source-payload endpoints.

## UI routes

The internal Next.js UI uses these routes:

| Route                           | Purpose                                                                     |
| ------------------------------- | --------------------------------------------------------------------------- |
| `/clients`                      | Reporting-client list with loading, empty, and safe error states.           |
| `/clients/[clientId]`           | Client details and effective-dated KPI list/create/edit section.            |
| `/clients/[clientId]/knowledge` | Knowledge grouped by category with provenance and manual create/edit forms. |

Editing an existing knowledge value requires an explicit confirmation before the request is sent.
There is no delete button and no authentication UI.

## Data contracts

Backend Pydantic models and shared TypeScript contracts use the same snake-case API field names.
Request models reject unexpected fields so callers cannot add `client_id`, source provenance, audit
timestamps, or other internal columns to a mutation payload.

### Clients

- `ClientSummary`: `id`, `name`, `slug`, `status`.
- `ClientDetails`: summary fields plus `reporting_timezone`, `default_currency`, `created_at`, and
  `updated_at`.

The top-level client list is the one intentional non-client-owned lookup. All data below a client
requires an explicit target client UUID.

### Knowledge

- `KnowledgeRecord` exposes reporting knowledge identity, `client_id`, category/key, JSON object
  value, status, safe source/version provenance, approval fields, version, and timestamps.
- `KnowledgeCreate` accepts only `category`, `knowledge_key`, `value`, and `status`.
- `KnowledgeUpdate` accepts only those same editable fields, requires at least one change, rejects
  blank/null required values, and cannot carry `client_id` or provenance fields.

The API returns mapped reporting knowledge, not an unfiltered source-database row. It does not
return source hashes, import batch ids, credentials, service keys, source URLs, or raw backend
errors.

### KPIs

- `KpiRecord` contains `id`, `client_id`, `metric_key`, `label`, nullable `target_value`, `unit`,
  `direction`, `attribution_level`, `active_from`, nullable `active_to`, and audit timestamps.
- `KpiCreate` accepts the schema fields above except server identities and timestamps.
- `KpiUpdate` accepts only editable KPI fields and requires at least one submitted change.

Safe errors use a stable code and message with optional field-level details. Internal Supabase
responses and exception text are never returned.

## Client scoping

Client-owned repository methods require `client_id` as an explicit keyword argument. Lists always
filter by that value. Record reads and writes filter by both the target `client_id` and record UUID.
Create payloads receive `client_id` from the nested route rather than request JSON. Update models
forbid extra fields, so a caller cannot move a record by submitting another client id.

The schema reinforces this design with non-null `client_id`, client-leading indexes, and composite
same-client foreign keys. Unknown clients and records return fixed safe `404` errors. These checks
provide logical isolation only; anyone who can reach this trusted service is not authenticated or
authorized by the application.

## Manual and imported knowledge

Manual creation always sets:

- `source_type` to `manual`;
- `source_identifier` and `source_version` to null;
- initial `version` to `1`.

Imported section knowledge retains its source type, source identifier, display name/reference,
source version, deterministic hash, import batch, and import timestamp in the database. The public
manual update contract omits those fields, so editing category, key, value, or status cannot
silently overwrite provenance or move the record to another client.

The UI labels manual and imported records separately. Imported provenance is displayed using safe
source/version metadata. No source hash, import batch, complete source response, or credential is
shown. There is no automatic or manual deletion path.

Editing an imported row is a reporting-side manual override, but it deliberately preserves the
four-column source identity. If an operator later runs an explicitly confirmed import for that same
`client_id`, source type, source identifier, and source version, the atomic upsert can replace the
source-managed fields again. This management layer never starts an import automatically. A durable
override/pinning policy is an unresolved contract decision.

## KPI validation and active state

The API and schema enforce only contract-supported structural rules:

- required text is trimmed and cannot be blank;
- labels are at most 120 characters;
- targets are nullable finite decimals;
- `active_from` is required and `active_to`, when present, cannot precede it;
- `(client_id, metric_key, active_from)` identifies an effective-dated KPI version;
- timestamps are created and maintained by the database.

The schema has no invented `is_active` field. Current activity is represented by the effective
date interval: a KPI is active when the current date is on or after `active_from` and not after a
non-null `active_to`.

Phase 0 has not approved finite catalogs for `metric_key`, `unit`, `direction`, or
`attribution_level`. Until those contracts are approved, the application validates them only as
non-empty strings and does not claim semantic allowlist validation. KPI actuals, comparisons, and
performance calculations are outside Phase 2.

## Two-client synthetic validation

Automated fixtures use two clearly de-identified clients, `Development Alpha` and
`Development Beta`, with fixed test UUIDs. Both deliberately have a knowledge row named
`shared_key` and a KPI named `shared_metric`; this proves separation comes from `client_id`, not
accidentally distinct business keys. Their additional structures differ:

- Alpha has synthetic `audience` knowledge and a currency/decrease cost-per-lead KPI;
- Beta has synthetic `offering` knowledge and a percent/increase qualification-rate KPI;
- knowledge and KPI record ids are distinct across the clients;
- all text is fabricated and contains no real company, person, source identifier, credential, or
  production payload.

The fixtures prove that Client A lists cannot contain Client B records, a Client A record cannot be
retrieved or updated through Client B, mutation payloads cannot change ownership, repository calls
always carry the route client id, and unknown clients return safe `404` responses. Fixtures live
only in automated tests; they are not migration seeds and are not applied to production.

## Live pilot status and safety

Read-only discovery confirmed `org_clients`, `org_knowledge_items`, and
`org_knowledge_base_sections` but found zero rows. No two approved pilot client identifiers or
populated source records were supplied. Consequently:

- live two-client knowledge validation is blocked;
- no real client was imported;
- no development fixture was applied to a live database;
- the knowledge Supabase received zero writes;
- its adapter still exposes no insert, update, upsert, delete, or RPC method.

Service-role keys remain backend-only and are absent from browser contracts, API responses, logs,
errors, snapshots, and fixtures.

## Phase 2 exit limitations

The Phase 2B management behavior and logical two-client separation can be validated locally, but
the original TRD Phase 2 exit criteria are not fully met:

1. "Users can access only assigned clients" cannot be claimed because this trusted MVP explicitly
   has no users, login, memberships, roles, authorization, or RLS.
2. "Cross-client RLS tests pass" cannot be claimed because no user-based RLS policies exist. The
   repository/API tests prove application-level client filtering instead.
3. "Two pilot clients have validated knowledge records" remains blocked until approved pilot
   identifiers and populated source records are supplied and a real import is separately approved.
4. KPI semantic catalogs and several free-form knowledge mappings remain unresolved Phase 0
   contract decisions.

Phase 2 therefore does not yet meet the complete original TRD exit criteria. Phase 3 must not be
started on the assumption that these external and architectural blockers have been resolved.
