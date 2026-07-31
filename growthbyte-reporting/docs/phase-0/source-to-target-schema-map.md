# Source-to-target schema map

Status: **proposed; approval required before migrations**. Target names are Phase 0 proposals, not existing tables. Every client-owned target row includes non-null `client_id`. The MVP has no users or user authorization; backend same-client validation is the separation boundary. Secrets remain backend-only.

| Source table | Proposed target table | Action | Required changes | Technical reason |
|---|---|---|---|---|
| `organizations` | none initially | Exclude/adapt later | Keep MVP single-operator and trusted-network scoped | Copying legacy organization/runtime coupling is unnecessary |
| `org_clients` | `clients` | Adapt | Remove operational UI settings; add timezone/currency/status; constrain fields | Canonical reporting client root |
| `profiles` | none for MVP | Exclude/defer | Do not copy identities, sessions, roles, or profile data | MVP has no users, login, authentication, or authorization |
| `client_members` | none for MVP | Exclude/defer | Do not create memberships or roles | User authorization is outside MVP scope |
| `staff_client_allowlist` | none for MVP | Exclude/defer | Replace no access semantics in Phase 0; enforce explicit backend `client_id` scope | No user permission matrix exists in MVP |
| `org_knowledge_items` | `client_knowledge` | Adapt later | Require `client_id`; add category/status/source/provenance and sensitivity | Preserve only an approved knowledge subset |
| `org_knowledge_base_sections` | `client_knowledge` and optional `client_knowledge_versions` | Split/adapt later | Flatten approved fields or preserve structured payload with schema version | Avoid copying UI-specific structure blindly |
| `org_knowledge_base_section_versions` | `client_knowledge_versions` | Adapt later | Immutable versions, optional operator label, reason, source hash, and `client_id` | Auditable knowledge changes without application users |
| `org_client_documents` | `knowledge_sources` | Adapt later | Separate object metadata from extracted text; define retention/classification | Source provenance and PII controls |
| `kb_field_comments`, `kb_thread_status` | optional `knowledge_review_events` | Adapt or exclude | Real FKs, `client_id`, append-only decisions, optional operator label | Existing text IDs and broad updates are fragile |
| `org_goals` | `client_goals` and `client_kpis` | Split | Separate narrative from metric definition; validate unit/direction/window | Deterministic reporting contract |
| `org_goal_metric_snapshots` | `metric_snapshots` | Adapt | Add `client_id`, KPI/period, formula version, input lineage, and quality status | Reproducible verified values |
| `ads_daily` | `meta_daily_performance` | Adapt | Replace account key with same-client FKs; retain raw actions separately; add currency/timezone/sync lineage | Client-scoped facts with traceability |
| `ads_platform_daily`, `ads_audience_daily` | optional performance-breakdown tables | Adapt later | Add `client_id`, account/entity FKs, and explicit grain | Useful dimensions, not initial core |
| `ads_targeting` | `meta_ad_sets` plus optional targeting snapshot | Split/adapt | Normalize campaign/ad-set; version time-varying targeting | Current-only legacy row loses history |
| no source table | `meta_accounts` | New | `client_id`, external account id/name/currency/timezone/status; no token | Account identity remains separate from secrets |
| no source table | `meta_campaigns`, `meta_ad_sets`, `meta_ads` | New | `client_id`, account FKs, external IDs, names/status, source timestamps | Required canonical dimensions are absent in legacy schema |
| `leads` | `sheet_raw_rows`, `normalised_leads`, `lead_attribution` | Split | Add `client_id`, config/sync lineage; encrypt/hash identifiers as needed; remove fixed enums | Raw evidence, normalized lead, and attribution have different lifecycles |
| none; legacy export code only | `google_sheet_configurations`, `sheet_column_mappings`, `lead_status_mappings` | New | Versioned, client-scoped configuration and mappings; no secret values | Pilot Sheets are not standardized |
| `sync_log`, `job_runs` | `sync_runs` | Adapt/merge | Add `client_id`, structured errors, watermark, counts, redacted details | One client-scoped observability contract |
| `org_google_integrations` | `google_sheet_configurations` | Adapt concept only | Keep Sheet id/tab/header/timezone; do not copy legacy GSC/GA4 fields or tokens | Google OAuth is Sheets-only in the reporting MVP |
| `org_google_credentials` | none copied | Exclude/defer | Existing knowledge/legacy credentials are not migrated; future Sheets OAuth material stays backend-only | No runtime legacy dependency or data copy is approved |
| `org_meta_credentials` | none copied | Exclude/defer | Use only the confirmed backend Meta token in later implementation; do not copy legacy credential rows | Credential migration/storage design is not Phase 0 implementation |
| `audit_client_access`, `auth_events` | optional `operational_events` | Exclude/adapt concept | Do not copy auth/user events; future events use process/run id and optional operator label | MVP has no authenticated users |
| no source table | `report_versions`, `report_approvals` | New | Immutable schema-versioned payload and append-only decision with optional operator label | Human review remains required without application accounts |
| legacy workflow/task/content/SEO/Instagram/execution tables | none | Exclude | No migration | Not required for standalone reporting runtime |

## Target rules frozen for the MVP

1. The reporting Supabase database is independent of the legacy application and existing knowledge Supabase at runtime.
2. Every client-owned target table has non-null `client_id` and a FK to `clients(id)`.
3. Same-client parent/child constraints and backend validation reject mixed-client inputs, joins, aggregates, outputs, caches, files, and reports.
4. The MVP has no application identity, user, membership, role, permission, or RLS user-authorization contract.
5. The MVP runs only locally or inside a trusted private network; public deployment is prohibited until later authentication/authorization work.
6. Supabase service-role credentials and all other confirmed secrets are backend-only and never returned to the browser.
7. Google OAuth is solely for a future Google Sheets connection and is not application login.
8. Existing knowledge Supabase is read-only during Phase 0 and is not connected, migrated, or copied at runtime.
9. External identifiers are unique only within their provider/account scope and are never accepted as client authority without an explicit mapping.
10. Raw source data preserves sync/source lineage; no executable target migration is created during Phase 0.

## Approval dependencies

This map cannot be frozen until the latest TRD is supplied, the knowledge migration strategy is selected, two pilot Sheet layouts are inspected, lead-status rules are confirmed, and pilot Meta account/field/permission availability is verified. A role matrix and RLS user-policy design are deliberately not approval dependencies.

