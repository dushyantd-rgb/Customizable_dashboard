# Canonical reporting data contract

Status: **proposed target contract; not approved**.

All field names in this document are proposed for the new database. They are not claims about the legacy database or missing pilot Sheets. The `Source` column states intended provenance. “Pilot mapping TBD” means the source field is unknown until samples are supplied.

Confirmed MVP constraint: there is no application identity model and therefore no target user, profile, membership, role, permission, or login entity. Human review evidence uses an optional operator label supplied by the trusted local process, not an authenticated user foreign key. RLS-based user authorization is deferred.

PII classes: `None`, `Indirect` (can identify an organization/account), `Personal`, `Contact`, and `Sensitive`. Secrets are deliberately absent from business entities.

Credential material is outside this canonical business-data contract. The only confirmed available categories are reporting Supabase credentials, read-only existing knowledge Supabase credentials, Google OAuth client ID/secret for a future Sheets connection, a Meta access token, and a GLM gateway key. None is a client-owned business field; none may reach the browser. Existing knowledge credentials do not authorize a runtime connection or data copy.

## Clients — `clients`

| Proposed field | Type | Req. | Source | Validation | PII | Notes |
|---|---|---:|---|---|---|---|
| `id` | `uuid` | Yes | System | UUID; immutable | None | Tenant key |
| `name` | `text` | Yes | Approved setup / legacy `org_clients.name` | Trimmed, 1–200 chars | Indirect | Display name |
| `slug` | `text` | Yes | System from approved name | lowercase unique pattern | Indirect | Non-secret routing label |
| `reporting_timezone` | `text` | Yes | Business confirmation | Valid IANA timezone | None | Governs day/period boundaries |
| `default_currency` | `char(3)` | Yes | Meta account or confirmation | ISO 4217 uppercase | None | No cross-currency sum without conversion |
| `status` | `text` | Yes | Operator | `active`,`paused`,`archived` | None | Archived data remains auditable |
| `created_at`, `updated_at` | `timestamptz` | Yes | System | UTC timestamps | None | Audit fields |

## Client knowledge — `client_knowledge`

| Proposed field | Type | Req. | Source | Validation | PII | Notes |
|---|---|---:|---|---|---|---|
| `id` | `uuid` | Yes | System | UUID | None | Knowledge record |
| `client_id` | `uuid` | Yes | Migration/operator | FK `clients` | Indirect | Logical client scope |
| `category` | `text` | Yes | Approved knowledge taxonomy | controlled value | None | E.g. brand, audience, offering; list TBD |
| `key` | `text` | Yes | Migration/operator | unique per `(client_id,category,key)` | None | Stable semantic key |
| `value` | `jsonb` | Yes | Legacy approved content or operator | schema-valid for category | Could contain PII | Never pass unreviewed data to agent |
| `status` | `text` | Yes | Reviewer | `draft`,`approved`,`retired` | None | Only approved content used in reports |
| `source_type` | `text` | Yes | System | `legacy`,`document`,`manual`,`derived` | None | Provenance |
| `source_reference` | `text` | No | Migration/source | non-secret reference | Indirect | No credentials or signed URLs |
| `version` | `integer` | Yes | System | >=1, monotonic | None | Immutable history recommended |
| `approved_by_label`, `approved_at` | `text`,`timestamptz` | No | Trusted review process | both null or both present; label is not an identity credential | Personal | Human approval evidence without application users |

## Client goals — `client_goals`

| Proposed field | Type | Req. | Source | Validation | PII | Notes |
|---|---|---:|---|---|---|---|
| `id` | `uuid` | Yes | System | UUID | None | Goal identity |
| `client_id` | `uuid` | Yes | Operator / approved legacy goal | FK `clients` | Indirect | Logical client scope |
| `name` | `text` | Yes | Business confirmation | 1–200 chars | None | Human-readable outcome |
| `description` | `text` | No | Business confirmation | length limit TBD | Could contain PII | Avoid personal data |
| `starts_on`, `ends_on` | `date` | No | Business confirmation | start <= end | None | Client timezone dates |
| `status` | `text` | Yes | Operator | `draft`,`active`,`complete`,`archived` | None | Reporting inclusion is explicit |

## Client KPIs — `client_kpis`

| Proposed field | Type | Req. | Source | Validation | PII | Notes |
|---|---|---:|---|---|---|---|
| `id` | `uuid` | Yes | System | UUID | None | KPI identity |
| `client_id` | `uuid` | Yes | Operator / approved legacy goal | FK `clients` | Indirect | Logical client scope |
| `goal_id` | `uuid` | No | Operator | FK same client | None | Optional goal link |
| `metric_key` | `text` | Yes | Approved metric catalog | controlled unique key | None | References deterministic formula |
| `label` | `text` | Yes | Operator | 1–120 chars | None | Display label |
| `target_value` | `numeric` | No | Business confirmation | finite decimal | None | Meaning set by direction/unit |
| `unit` | `text` | Yes | Metric catalog | approved unit enum | None | e.g. count, percent, currency |
| `direction` | `text` | Yes | Metric catalog | `increase`,`decrease`,`range` | None | Evaluation semantics |
| `attribution_level` | `text` | Yes | Business confirmation | approved level enum | None | Client/campaign/ad-set/ad |
| `active_from`, `active_to` | `date` | Yes/No | Operator | valid interval | None | Version instead of overwriting semantics |

## Meta accounts — `meta_accounts`

| Proposed field | Type | Req. | Source | Validation | PII | Notes |
|---|---|---:|---|---|---|---|
| `id` | `uuid` | Yes | System | UUID | None | Internal id |
| `client_id` | `uuid` | Yes | Approved account link | FK `clients` | Indirect | Logical client scope |
| `external_account_id` | `text` | Yes | Meta API | digits/string format confirmed by API | Indirect | Unique per provider |
| `name` | `text` | No | Meta API | trimmed | Indirect | Display only |
| `currency` | `char(3)` | Yes | Meta API | ISO 4217 | None | Spend currency |
| `account_timezone` | `text` | Yes | Meta API | valid Meta/IANA mapping | None | Insight day boundary |
| `status` | `text` | Yes | Meta API | mapped controlled enum | None | Preserve raw status separately if needed |
| `last_seen_at` | `timestamptz` | Yes | Sync | UTC | None | Freshness |

Token material belongs in a service-only credential store and is not part of this contract.

## Campaigns — `meta_campaigns`

| Proposed field | Type | Req. | Source | Validation | PII | Notes |
|---|---|---:|---|---|---|---|
| `id` | `uuid` | Yes | System | UUID | None | Internal id |
| `client_id` | `uuid` | Yes | Parent account | FK `clients` | Indirect | Logical client scope |
| `meta_account_id` | `uuid` | Yes | Parent account | FK same client | Indirect | Account scope |
| `external_campaign_id` | `text` | Yes | Meta API | unique per account | Indirect | Exact attribution key |
| `name` | `text` | No | Meta API | preserve source text | Indirect | Names are not stable keys |
| `objective`, `status`, `effective_status` | `text` | No | Meta API | mapped plus raw preservation | None | Permissions/fields need confirmation |
| `source_created_at`, `source_updated_at` | `timestamptz` | No | Meta API | valid timestamps | None | Source lifecycle |

## Ad sets — `meta_ad_sets`

| Proposed field | Type | Req. | Source | Validation | PII | Notes |
|---|---|---:|---|---|---|---|
| `id` | `uuid` | Yes | System | UUID | None | Internal id |
| `client_id` | `uuid` | Yes | Parent account | FK `clients` | Indirect | Logical client scope |
| `meta_account_id`, `campaign_id` | `uuid` | Yes | Parent entities | FKs same client/account | Indirect | Hierarchy |
| `external_ad_set_id` | `text` | Yes | Meta API | unique per account | Indirect | Exact attribution key |
| `name` | `text` | No | Meta API | preserve source text | Indirect | Not a match key unless low-confidence review |
| `status`, `effective_status` | `text` | No | Meta API | mapped/raw | None | Current source state |
| `targeting_snapshot` | `jsonb` | No | Meta API | allowlisted keys; no custom-audience PII | Sensitive | Optional/current; history design TBD |

## Ads — `meta_ads`

| Proposed field | Type | Req. | Source | Validation | PII | Notes |
|---|---|---:|---|---|---|---|
| `id` | `uuid` | Yes | System | UUID | None | Internal id |
| `client_id` | `uuid` | Yes | Parent account | FK `clients` | Indirect | Logical client scope |
| `meta_account_id`, `campaign_id`, `ad_set_id` | `uuid` | Yes | Parent entities | FKs same hierarchy | Indirect | Entity chain |
| `external_ad_id` | `text` | Yes | Meta API | unique per account | Indirect | Exact attribution key |
| `name` | `text` | No | Meta API | preserve source text | Indirect | Display only |
| `creative_id` | `text` | No | Meta API | external id format | Indirect | Permission availability TBD |
| `status`, `effective_status` | `text` | No | Meta API | mapped/raw | None | Current state |

## Daily Meta performance — `meta_daily_performance`

Grain: one client + account + report date + entity level/entity + optional breakdown set.

| Proposed field | Type | Req. | Source | Validation | PII | Notes |
|---|---|---:|---|---|---|---|
| `id` | `uuid` | Yes | System | UUID | None | Surrogate identity |
| `client_id` | `uuid` | Yes | Account link | FK `clients` | Indirect | Logical client scope |
| `meta_account_id` | `uuid` | Yes | Meta account | FK same client | Indirect | Source account |
| `report_date` | `date` | Yes | Meta Insights | in account timezone | None | Never infer browser timezone |
| `entity_level` | `text` | Yes | Sync request | `account`,`campaign`,`ad_set`,`ad` | None | Grain declaration |
| `entity_id` | `uuid` | No | Resolved dimension | FK appropriate entity | Indirect | Null only for account level |
| `spend` | `numeric(20,6)` | Yes | Meta Insights | >=0 | None | In `currency` |
| `currency` | `char(3)` | Yes | Meta account | ISO 4217 | None | Stored on every fact for audit |
| `impressions`, `reach`, `clicks`, `meta_leads`, `meta_conversions` | `bigint` | Yes | Meta Insights/actions | >=0 | None | Action definitions versioned |
| `conversion_value` | `numeric(20,6)` | No | Meta action values | >=0 | None | Currency required |
| `raw_metrics` | `jsonb` | Yes | Meta API | allowlisted payload; no token | None | Traceability, not browser default |
| `sync_run_id` | `uuid` | Yes | Sync | FK same client | None | Lineage |
| `source_updated_at` | `timestamptz` | No | Meta API if available | UTC | None | Late-change handling |

## Google Sheet configurations — `google_sheet_configurations`

| Proposed field | Type | Req. | Source | Validation | PII | Notes |
|---|---|---:|---|---|---|---|
| `id` | `uuid` | Yes | System | UUID | None | Configuration id |
| `client_id` | `uuid` | Yes | Approved setup | FK `clients` | Indirect | Logical client scope |
| `spreadsheet_id` | `text` | Yes | Google Sheets setup | ID only, not URL | Indirect | Not a credential |
| `worksheet_name` | `text` | Yes | Pilot setup | non-empty | Indirect | Exact tab name |
| `header_row` | `integer` | Yes | Pilot inspection | >=1 | None | Default must be confirmed, not assumed |
| `data_start_row` | `integer` | Yes | Pilot inspection | > header row | None | Parsing boundary |
| `source_timezone` | `text` | Yes | Sheet owner/inspection | valid IANA timezone | None | Date parsing |
| `status` | `text` | Yes | Operator | `draft`,`active`,`paused`,`error` | None | No sync while draft |
| `oauth_connection_key` | `text` | No | Future backend setup | opaque backend reference; never secret material | Sensitive | Google OAuth is Sheets-only and not application login |
| `mapping_version` | `integer` | Yes | System | >=1 | None | Pins mappings used by each sync |

## Column mappings — `sheet_column_mappings`

| Proposed field | Type | Req. | Source | Validation | PII | Notes |
|---|---|---:|---|---|---|---|
| `id` | `uuid` | Yes | System | UUID | None | Mapping id |
| `client_id` | `uuid` | Yes | Parent config | FK `clients` | Indirect | Logical client scope |
| `sheet_configuration_id` | `uuid` | Yes | Parent config | FK same client | Indirect | Configuration scope |
| `source_header` | `text` | Yes | Pilot Sheet | exact header, normalized comparison allowed | Could reveal PII | Original preserved |
| `canonical_field` | `text` | Yes | Approved mapping | allowlisted lead field | None | No arbitrary SQL field |
| `transform` | `jsonb` | Yes | Approved mapping | schema-valid deterministic transform | None | No executable code |
| `required` | `boolean` | Yes | Contract | boolean | None | Missing required header fails sync |
| `version` | `integer` | Yes | System | >=1; immutable | None | Reproducibility |

## Lead-status mappings — `lead_status_mappings`

| Proposed field | Type | Req. | Source | Validation | PII | Notes |
|---|---|---:|---|---|---|---|
| `id` | `uuid` | Yes | System | UUID | None | Mapping id |
| `client_id` | `uuid` | Yes | Parent config | FK `clients` | Indirect | Logical client scope |
| `sheet_configuration_id` | `uuid` | Yes | Parent config | FK same client | Indirect | Sheet-specific |
| `source_value_normalized` | `text` | Yes | Pilot values | trim/case/space normalization | None | Raw value retained separately |
| `canonical_status` | `text` | Yes | Approved rules | six-status enum | None | See status contract |
| `counts_as_reviewed` | `boolean` | Yes | Approved rules | consistent with canonical status | None | Derived/configured explicitly |
| `mapping_version` | `integer` | Yes | System | >=1; immutable | None | Historical reproducibility |
| `approved_by_label`, `approved_at` | `text`,`timestamptz` | Yes | Trusted review process | non-empty label and valid time | Personal | Manual operator label, not an application user |

## Raw Sheet rows — `sheet_raw_rows`

| Proposed field | Type | Req. | Source | Validation | PII | Notes |
|---|---|---:|---|---|---|---|
| `id` | `uuid` | Yes | System | UUID | None | Raw row id |
| `client_id` | `uuid` | Yes | Config | FK `clients` | Indirect | Logical client scope |
| `sheet_configuration_id`, `sync_run_id` | `uuid` | Yes | Sync | FKs same client | Indirect | Lineage |
| `worksheet_name`, `row_number` | `text`,`integer` | Yes | Sheets API | row >= data start | Indirect | Source position |
| `source_row_key` | `text` | Yes | System | stable hash of config/tab/row/version | Sensitive | Dedup key; avoid raw PII in key |
| `raw_values` | `jsonb` | Yes | Sheets API | exact header/value representation | Contact/Personal | Restricted; no agent access by default |
| `row_hash` | `text` | Yes | System | SHA-256 or approved hash | Sensitive | Change detection |
| `observed_at` | `timestamptz` | Yes | Sync | UTC | None | Ingestion time |
| `is_deleted_at_source` | `boolean` | Yes | Reconciliation | boolean | None | No destructive history loss |

## Normalised leads — `normalised_leads`

| Proposed field | Type | Req. | Source | Validation | PII | Notes |
|---|---|---:|---|---|---|---|
| `id` | `uuid` | Yes | System | UUID | None | Lead identity |
| `client_id` | `uuid` | Yes | Parent config | FK `clients` | Indirect | Logical client scope |
| `raw_sheet_row_id` | `uuid` | Yes | Normalizer | FK same client | None | Evidence link |
| `source_lead_id` | `text` | No | Pilot mapping TBD | trimmed; source-scoped | Indirect | Not assumed available |
| `meta_lead_id` | `text` | No | Pilot mapping TBD | Meta identifier validation | Indirect | Exact attribution candidate |
| `lead_at` | `timestamptz` | No | Pilot mapping TBD | timezone-aware parse | None | Required for date-window matching |
| `name` | `text` | No | Pilot mapping TBD | normalize whitespace | Personal | Minimize downstream use |
| `phone_e164` | `text` | No | Pilot mapping TBD | E.164; encrypted/tokenized storage decision | Contact | Never log full value |
| `email_normalized` | `text` | No | Pilot mapping TBD | valid normalized email | Contact | Hash for matching where appropriate |
| `source_status_raw` | `text` | No | Pilot status column | preserve exact input | None | Mapping evidence |
| `canonical_status` | `text` | Yes | Versioned status mapping | six-status enum | None | Unknown/blank -> `not_reviewed` |
| `is_reviewed` | `boolean` | Yes | Deterministic status rule | consistent with mapping version | None | Metric input |
| `qualification_at`, `conversion_at` | `timestamptz` | No | Pilot mapping TBD | >= lead time when known | None | No invented dates |
| `mapping_version` | `integer` | Yes | Config | >=1 | None | Reproducibility |

## Lead attribution — `lead_attribution`

| Proposed field | Type | Req. | Source | Validation | PII | Notes |
|---|---|---:|---|---|---|---|
| `id` | `uuid` | Yes | System | UUID | None | Attribution result |
| `client_id` | `uuid` | Yes | Lead | FK `clients` | Indirect | Logical client scope |
| `lead_id` | `uuid` | Yes | Normalized lead | FK same client; one active decision | None | Subject |
| `meta_account_id`, `campaign_id`, `ad_set_id`, `ad_id` | `uuid` | No | Deterministic matcher | FKs same client/hierarchy | Indirect | Only levels supported by evidence are populated |
| `method` | `text` | Yes | Matcher | `exact_id`,`utm`,`name_date`,`client_only`,`unmatched` | None | Never silently promote confidence |
| `confidence` | `numeric(5,4)` | No | Approved matcher | 0–1; null for exact/unmatched allowed | None | Thresholds versioned |
| `matched_identifiers` | `jsonb` | Yes | Matcher | allowlisted, redacted evidence | Sensitive | No raw phone/email |
| `rule_version` | `text` | Yes | Deployed deterministic code | immutable version | None | Reproducibility |
| `review_status`, `reviewed_by_label`, `reviewed_at` | `text`,`text`,`timestamptz` | Yes/No | Trusted review process | coherent state; label is not an authenticated identity | Personal | Required for lower-confidence approval |

## Sync runs — `sync_runs`

| Proposed field | Type | Req. | Source | Validation | PII | Notes |
|---|---|---:|---|---|---|---|
| `id` | `uuid` | Yes | System | UUID | None | Run identity |
| `client_id` | `uuid` | Yes | Integration config | FK `clients` | Indirect | Logical client scope; one run per client batch |
| `source_type` | `text` | Yes | Orchestrator | `meta`,`google_sheets`,`normalization`,`metrics` | None | Stage/source |
| `configuration_id` | `uuid` | No | Orchestrator | valid same-client config | Indirect | Source config |
| `status` | `text` | Yes | Orchestrator | `queued`,`running`,`succeeded`,`partial`,`failed`,`cancelled` | None | Terminal transitions enforced |
| `started_at`, `finished_at` | `timestamptz` | Yes/No | System | finish >= start | None | UTC |
| `watermark_from`, `watermark_to` | `timestamptz` | No | Source cursor/window | ordered | None | Incremental lineage |
| `rows_read`, `rows_written`, `rows_rejected` | `bigint` | Yes | Stage | >=0 | None | Reconciliation |
| `error_code`, `error_summary` | `text` | No | Stage | redacted/allowlisted | None | No tokens, payloads, or PII |
| `initiated_by_label` | `text` | No | Local process/operator | non-secret free-text label | Personal | Not an authenticated user identity |

## Metric snapshots — `metric_snapshots`

| Proposed field | Type | Req. | Source | Validation | PII | Notes |
|---|---|---:|---|---|---|---|
| `id` | `uuid` | Yes | System | UUID | None | Immutable snapshot |
| `client_id` | `uuid` | Yes | KPI | FK `clients` | Indirect | Logical client scope |
| `kpi_id` | `uuid` | No | KPI configuration | FK same client | None | Optional for standard platform metric |
| `metric_key` | `text` | Yes | Metric catalog | approved key | None | Formula reference |
| `period_start`, `period_end` | `timestamptz` | Yes | Calculation | ordered; client timezone boundaries recorded | None | Half-open interval recommended |
| `attribution_level`, `entity_id` | `text`,`uuid` | Yes/No | Calculation | entity required below client level | Indirect | Scope |
| `value` | `numeric` | No | SQL/Python | finite; null allowed for unavailable | None | Zero is not “unavailable” |
| `unit`, `currency` | `text`,`char(3)` | Yes/No | Contract/source | approved unit; currency when monetary | None | No mixed-currency value |
| `numerator`, `denominator` | `numeric` | No | SQL/Python | preserve components | None | Explainability/QA |
| `formula_version` | `text` | Yes | Code release | immutable | None | Deterministic lineage |
| `input_cutoff_at`, `calculated_at` | `timestamptz` | Yes | Calculator | UTC | None | Late data reproducibility |
| `quality_status`, `quality_reasons` | `text`,`jsonb` | Yes | Calculator | controlled status/reason codes | None | `verified`,`partial`,`unavailable` |

## Report versions — `report_versions`

| Proposed field | Type | Req. | Source | Validation | PII | Notes |
|---|---|---:|---|---|---|---|
| `id` | `uuid` | Yes | System | UUID | None | Immutable report version |
| `client_id` | `uuid` | Yes | Report request | FK `clients` | Indirect | Logical client scope |
| `report_key`, `version` | `uuid`,`integer` | Yes | System | unique pair; version >=1 | None | Logical report + version |
| `period_start`, `period_end` | `timestamptz` | Yes | Report request | ordered | None | Reporting window |
| `schema_version` | `text` | Yes | Report schema package | supported version | None | Payload validation |
| `metric_snapshot_ids` | `uuid[]` | Yes | Report builder | all same client/period-compatible | None | Verified inputs |
| `content` | `jsonb` | Yes | Deterministic builder + GLM explanation later | schema-valid; no unsupported claims | Could contain PII | GLM text separated/tagged within schema |
| `status` | `text` | Yes | Workflow | `draft`,`in_review`,`approved`,`superseded` | None | Publishing gate |
| `generated_at`, `generated_by_label` | `timestamptz`,`text` | Yes/No | System/local process | UTC; optional non-secret label | Personal | Operational evidence without application users |

## Report approvals — `report_approvals`

| Proposed field | Type | Req. | Source | Validation | PII | Notes |
|---|---|---:|---|---|---|---|
| `id` | `uuid` | Yes | System | UUID | None | Append-only decision |
| `client_id` | `uuid` | Yes | Report | FK `clients` | Indirect | Logical client scope |
| `report_version_id` | `uuid` | Yes | Review | FK same client | None | Exact version reviewed |
| `decision` | `text` | Yes | Reviewer | `approved`,`changes_requested`,`rejected`,`approval_revoked` | None | Never overwrite prior decision |
| `comment` | `text` | No | Reviewer | required for negative/revoked outcomes | Could contain PII | Warn reviewers not to paste lead PII |
| `decided_by_label`, `decided_at` | `text`,`timestamptz` | Yes | Trusted review process | non-empty label; UTC | Personal | Human evidence without application users |
| `content_hash` | `text` | Yes | System | hash of exact report payload | Sensitive | Prevent approval/content mismatch |

## Contract-wide constraints

- Timestamps are stored as `timestamptz` in UTC; source/client/account timezone is stored and used to derive boundaries.
- Raw data is preserved; normalisation and attribution are versioned, deterministic transformations.
- Unknown or absent values stay null/unavailable and are never converted to zero unless zero was observed.
- No credential, access token, refresh token, service-role key, encryption key, or GLM key appears in these business tables.
- Cross-client foreign keys must be prevented with composite constraints or validated service logic plus database tests.
- Every ingestion, join, metric, report, export, cache, file, and agent/MCP context is bound to exactly one `client_id`; conflicting client scope is rejected.
- The MVP defines no users, profiles, memberships, roles, permissions, login fields, or RLS user-authorization acceptance criteria.
- Source deletion does not erase audit history; retention and cryptographic erasure rules await approval.
