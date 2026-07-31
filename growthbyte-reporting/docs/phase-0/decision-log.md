# Phase 0 decision log

Status values: `Confirmed`, `Proposed`, `Open`, or `Superseded`.

| ID | Status | Decision | Evidence / rationale | Consequence |
|---|---|---|---|---|
| D-001 | Confirmed | Build `growthbyte-reporting` as a standalone project | Setup brief | No legacy runtime dependency |
| D-002 | Confirmed | Use a separate reporting Supabase PostgreSQL database | Setup brief | Legacy/knowledge databases are discovery sources only |
| D-003 | Confirmed | Phase 0 produces contracts and a shell, not feature code | Setup brief | No apps, OAuth flows, ingestion, migrations, dashboard, agent, MCP, or PDF implementation |
| D-004 | Confirmed | Every client-owned target record contains non-null `client_id` | Confirmed MVP decision | Direct logical client scope is mandatory |
| D-005 | Superseded | Supabase RLS user authorization must be approved in Phase 0 | Replaced by D-017 and D-018 | RLS/user authorization no longer blocks Phase 0 |
| D-006 | Confirmed | Supabase service-role credentials are backend-only | Confirmed MVP decision | No service-role value in browser bundles, responses, logs, reports, or agent input |
| D-007 | Confirmed | SQL/Python calculates authoritative metrics | Setup brief | GLM explains verified snapshots only |
| D-008 | Confirmed | No guessed lead attribution | Setup brief | Unmatched/client-only data remains visibly unmatched |
| D-009 | Proposed | Use UUID internal ids plus provider-scoped external ids | Consistent FKs and source identity | Requires schema approval |
| D-010 | Proposed | Preserve raw data and version mappings, attribution, and formulas | Reproducible audits and late-data handling | Requires retention decisions |
| D-011 | Proposed | Return unavailable/null for zero denominators and missing inputs | Avoid misleading zero metrics | Report schema supports quality reasons |
| D-012 | Proposed | Qualification rate uses reviewed leads; review coverage exposes backlog | Separates outcome quality from operational completeness | Business confirmation required |
| D-013 | Open | Converted leads imply qualification without double counting | Funnel semantics not supplied | Blocks final qualification/conversion formulas |
| D-014 | Superseded | MVP user access is controlled through memberships and roles | Replaced by D-017 | No MVP user/membership data model |
| D-015 | Open | Which legacy knowledge forms may later migrate | Free-form items, structured sections, versions, documents, and comments overlap | Blocks knowledge target freeze |
| D-016 | Proposed | Metrics compare with the preceding equal-duration period | Deterministic default | Business/reporting approval required |
| D-017 | Confirmed | MVP has no application login, authentication, authorization, users, memberships, roles, or permission matrix | Confirmed MVP decision | Anyone with network/process access is a trusted operator; public deployment prohibited |
| D-018 | Confirmed | RLS-based user authorization is deferred and is not a Phase 0 sign-off criterion | Confirmed MVP decision | Replace RLS acceptance with client-scoping/no-data-mixing checks |
| D-019 | Confirmed | MVP runs only locally or inside a trusted private network | Confirmed MVP decision | Public exposure waits for later authentication/authorization work |
| D-020 | Confirmed | Google OAuth is only for connecting Google Sheets | Confirmed MVP decision | It must not create sessions or act as application login |
| D-021 | Confirmed | Available credential categories are limited to reporting Supabase, read-only knowledge Supabase, Google OAuth client ID/secret, Meta token, and GLM gateway key | Confirmed credential inventory | Extra `.env.example` placeholders are neither available nor approved credentials |
| D-022 | Confirmed | Existing knowledge Supabase inspection is read-only in Phase 0 | Confirmed MVP decision | No runtime connection, migration, or copy yet |
| D-023 | Confirmed | Backend operations must enforce same-client inputs and outputs | Confirmed MVP decision | Cross-client joins, cache keys, exports, metrics, and reports must fail validation |
| D-024 | Confirmed | Silpa, SuperK, and all legacy accounts remain unconfirmed as pilots | Confirmed pilot rule | Pilot classification requires explicit selection |

Only confirmed decisions are frozen. Proposed and open decisions remain Phase 0 review items; superseded decisions must not be used as acceptance criteria.

