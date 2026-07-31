# Security and client-separation contract

Status: **MVP boundary confirmed; retention and operational details remain open**.

## MVP trust boundary

The MVP has no application login, authentication, authorization, user accounts, memberships, roles, or permission matrix. It may run only on a developer machine or inside a trusted private network. Anyone able to reach the application or its host must be treated as a trusted operator with full MVP capability.

Public deployment, internet exposure, multi-user access control, application sessions, social login, and user-level audit identity are out of scope. They require a later security design and implementation before the deployment boundary changes.

Google OAuth is exclusively an integration mechanism for connecting Google Sheets. It must not create an application identity, session, membership, or login flow.

## Logical client separation

Absence of user authorization does not permit data mixing. Every client-owned record must contain non-null `client_id` referencing the target `clients` table.

Phase 0 acceptance criteria are:

1. Every client-owned target table explicitly includes `client_id`.
2. Parent/child relationships cannot link different clients; use same-client composite constraints where practical and deterministic backend validation everywhere.
3. Every ingestion, normalization, attribution, metric, report, export, cache, file path, and MCP/agent context is created for exactly one resolved `client_id`.
4. A backend operation rejects missing, conflicting, or mixed client identifiers before reading or writing business data.
5. Source account/Sheet identifiers are mapped to one client explicitly; legacy names or `account_key` values are never treated as authority by themselves.
6. Aggregations and joins include `client_id` predicates and test fixtures contain colliding external IDs across clients to prove isolation.
7. Outputs record their `client_id` and may reference only same-client source rows/snapshots.

The MVP must have automated no-data-mixing tests before feature completion in a later phase. Phase 0 defines the checks but does not implement them.

## RLS deferral

RLS-based user authorization is deferred and must not block Phase 0 sign-off. Phase 0 does not require a user policy matrix or RLS acceptance tests.

The MVP should avoid direct browser-to-Supabase business-data access. Its backend is the trusted data boundary and enforces `client_id` scoping. Before any public or untrusted-network deployment, authentication, authorization, least-privilege database access, RLS policies, and their isolation tests become mandatory design gates.

## Backend credential boundary

Supabase service-role credentials are backend-only. They must never be:

- prefixed with `NEXT_PUBLIC_` or bundled into browser code;
- returned by API responses or embedded in HTML, client logs, exports, report payloads, or source maps;
- passed to the GLM, MCP output, analytics, error trackers, or support artifacts;
- stored in ordinary client/business rows.

The backend loads secrets from local/trusted runtime configuration, validates `client_id` for every operation, and logs only redacted status information. The browser calls the backend and never receives a service-role value.

## Confirmed credential inventory

Only these credential categories are confirmed as available:

| Credential | Phase 0/MVP boundary |
|---|---|
| Reporting Supabase credentials | Backend-only for the new reporting database; Phase 0 does not create production migrations |
| Existing knowledge Supabase credentials | Read-only Phase 0 inspection only; no runtime dependency, migration, write, or data copy |
| Google OAuth client ID and secret | Future Google Sheets connection only; client secret is backend-only and OAuth is not app login |
| Meta access token | Backend-only; no Meta connection or ingestion is implemented in Phase 0 |
| GLM gateway key | Backend-only; no report agent is implemented in Phase 0 |

Variables or placeholders beyond this list in `.env.example` do not prove that additional credentials exist or are approved. No real credential value belongs in the repository.

## Existing knowledge Supabase

Read-only inspection is allowed during Phase 0 when it is needed to validate the knowledge model. Inspection must not mutate schema/data, create triggers/functions/policies, rotate credentials, or run application workflows. Query output containing client data or PII must not be committed.

The reporting MVP must not open a runtime connection to the knowledge Supabase. A migration/copy strategy, selected knowledge scope, provenance rules, and validation plan require separate Phase 0 approval before any later implementation.

## PII and source-data handling

- Raw Sheet rows, names, phone numbers, emails, messages, and custom-audience data are restricted even on a trusted network.
- Collect only fields needed for reporting; prefer normalized, hashed, or tokenized identifiers for deterministic matching.
- Reports and dashboards default to aggregates. Row-level lead data must not be included unless the reporting requirement explicitly needs it.
- Non-production examples use synthetic or irreversibly de-identified data.
- Exports stay inside the trusted boundary, use safe filenames, and avoid secrets.

## Logging and operational evidence

Structured logs allowlist fields. Redact authorization headers, cookies, OAuth codes/tokens, service keys, Sheet cell values, phone/email/name/message data, database URLs, ciphertext, and GLM prompts containing client information. Error summaries use safe codes.

Because the MVP has no users, operational events record a process/run identifier and optional manually supplied operator label—not an authenticated user identity. Useful events include configuration changes, sync attempts, attribution overrides, metric/report generation, report decisions, exports, and failures. Authentication, membership, role-change, and permission audit events are out of scope.

## Agent and MCP boundaries

- A future GLM receives only approved knowledge and verified aggregate metric snapshots for one `client_id`.
- It cannot access credentials, arbitrary tables, raw lead PII, or calculate authoritative metrics.
- Generated text remains untrusted draft content and cannot change verified metric values.
- Future MCP tools receive client scope from trusted backend configuration; each call is bound to one `client_id` and uses bounded, same-client queries.
- Agent/MCP caches, traces, prompts, and outputs include client scope and cannot be shared across clients.

No agent or MCP functionality is implemented during Phase 0.

## Retention questions requiring approval

- Raw Sheet row and Meta payload retention.
- Normalized lead/contact retention and deletion behavior.
- Metric, report, attribution, and operational-event retention.
- Backup retention and deletion verification.
- GLM provider retention/training terms and prompt/response storage.
- Export lifetime inside the trusted network.

## Phase 0 security sign-off gate

Phase 0 security review confirms the local/trusted-network boundary, exact credential inventory, backend-only secrets, explicit `client_id` on client-owned records, no-data-mixing acceptance criteria, PII/log-redaction rules, and the prohibition on public deployment. A role matrix and RLS user policies are deliberately not required for Phase 0 sign-off.

