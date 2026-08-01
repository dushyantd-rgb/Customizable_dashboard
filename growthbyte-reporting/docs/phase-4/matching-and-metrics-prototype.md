# Phase 4 matching and metrics prototype

Status: **implemented prototype; live validation and Phase 5 remain deferred**.

## Scope

Phase 4 implements:

- Raw Sheet-row normalisation into canonical lead records
- Deterministic attribution matching with confidence categories
- Match evidence and unmatched/duplicate review APIs
- Verified metric calculations from approved contracts
- Previous-period and KPI comparison
- Frozen metric snapshots with versioning
- Minimal internal metrics UI

Phase 4 does **not** implement:

- GLM or Anthropic calls
- MCP tools
- Generated recommendations
- PDF reports
- Scheduled sync
- Campaign or budget changes
- Fuzzy or AI-powered matching
- Phase 5 agent integration

## Normalisation rules

**Core requirements:**

1. Every operation requires explicit `client_id`
2. Raw source rows are preserved unchanged in `raw_sheet_rows`
3. Dates are normalised using the client's `reporting_timezone`
4. Booleans are parsed safely (true/false, yes/no, 1/0)
5. Lead status uses the client's versioned status mappings
6. Unknown status values become `not_reviewed` with validation warnings
7. Campaign, ad-set, ad, and UTM fields are normalised and trimmed
8. Stable source identifiers are preserved when available
9. Repeated processing is deterministic and idempotent

**Field normalisation:**

| Canonical field | Normalisation |
|---|---|
| `source_lead_id` | Trim; preserve null |
| `lead_at` | Parse in source timezone; store as UTC timestamptz |
| `campaign_id`, `campaign_name` | Trim; null if empty |
| `adset_id`, `adset_name` | Trim; null if empty |
| `ad_id`, `ad_name` | Trim; null if empty |
| `utm_*` fields | Trim, lowercase; null if empty |
| `lead_status` | Use status mapping; preserve raw in `source_status_raw` |
| `is_reviewed` | Derived from status mapping `counts_as_reviewed` |

**Validation warnings:**

- `missing_lead_date`: Lead date is null or unparseable
- `missing_lead_identifier`: No source_lead_id or other identifier
- `unknown_status`: Source status not in mapping
- `invalid_boolean`: Boolean field could not be parsed
- `invalid_date`: Date field could not be parsed
- `missing_attribution_fields`: No campaign/ad ID or UTM fields
- `duplicate_source_row`: Same `source_row_key` already processed
- `changed_source_row_hash`: Row content changed but key matches

## Matching priority and confidence

Matching is strictly deterministic. No fuzzy matching, semantic similarity, or GLM matching is used.

**Priority order:**

1. **Exact Meta ad ID**: `lead_records.meta_lead_id` matches `meta_ads.external_ad_id` for the same client
   - Method: `exact_ad_id`
   - Confidence: 1.0
   - Entity level: `ad`

2. **Exact Meta ad-set ID**: Ad-set ID matches `meta_ad_sets.external_ad_set_id`
   - Method: `exact_ad_set_id`
   - Confidence: 0.95
   - Entity level: `ad_set`

3. **Exact Meta campaign ID**: Campaign ID matches `meta_campaigns.external_campaign_id`
   - Method: `exact_campaign_id`
   - Confidence: 0.9
   - Entity level: `campaign`

4. **Exact UTM match**: UTM identifiers match a unique Meta entity for the client and period
   - Method: `utm_match`
   - Confidence: 0.85
   - Entity level: Most specific match (ad > ad_set > campaign)

5. **Unique name match**: Normalised name matches exactly one candidate for that client and period
   - Method: `unique_name`
   - Confidence: 0.7
   - Entity level: Based on matched entity
   - Requires: No other candidates with same name

6. **Unmatched**: No match found or candidates are ambiguous
   - Method: `unmatched`
   - Confidence: null
   - Entity level: `client_only`

**Ambiguity handling:**

- Multiple candidates for the same identifier → unmatched
- Name match with more than one candidate → unmatched
- Conflicting signals (e.g., UTM matches different entity than ID) → prefer higher priority exact ID match
- Cross-client identifiers → never matched (filtered by `client_id`)

**Evidence storage:**

- `matched_identifiers`: JSONB with non-PII evidence (IDs, normalized names, match method)
- `candidate_count`: Number of candidates considered
- `review_status`: `automatic`, `manual_approved`, `manual_rejected`

## Metric formulas

All metrics follow `metric-contract.md`. Division by zero returns null, not zero or infinity.

| Metric key | Formula | Unit | Notes |
|---|---|---|---|
| `spend` | `sum(meta_daily_insights.spend)` | currency | Aggregated by scope |
| `impressions` | `sum(impressions)` | count | |
| `reach` | `sum(reach)` | count | May be null |
| `clicks` | `sum(clicks)` | count | |
| `meta_leads` | `sum(meta_leads)` | count | Meta-reported |
| `imported_leads` | `count(lead_records)` | count | Sheet-imported |
| `qualified_leads` | `count(canonical_status = 'qualified' or 'converted')` | count | Per status contract |
| `disqualified_leads` | `count(canonical_status = 'disqualified')` | count | |
| `invalid_leads` | `count(canonical_status = 'invalid')` | count | |
| `converted_leads` | `count(canonical_status = 'converted')` | count | |
| `cost_per_lead` | `spend / meta_leads` | currency | Null if zero leads |
| `cost_per_qualified_lead` | `attributed_spend / attributed_qualified_leads` | currency | Attribution-dependent |
| `qualification_rate` | `qualified_plus_converted / reviewed_leads * 100` | percent | Null if zero reviewed |
| `conversion_rate` | `converted_leads / qualified_plus_converted * 100` | percent | Null if zero qualified |
| `ctr` | `clicks / impressions * 100` | percent | Null if zero impressions |
| `cpc` | `spend / clicks` | currency | Null if zero clicks |
| `cpm` | `spend / impressions * 1000` | currency | Null if zero impressions |
| `unmatched_leads` | `count(method = 'unmatched')` | count | |
| `attribution_coverage` | `matched_leads / total_leads * 100` | percent | |

**Currency handling:**

- Metrics are calculated in the client's `default_currency`
- Mixed-currency data produces partial quality status
- No currency conversion without approved FX source

**Period boundaries:**

- Use client's `reporting_timezone`
- Half-open interval: `[period_start, period_end)`
- Meta insights use `report_date` in account timezone
- Lead dates use `lead_at` in UTC, converted to client timezone for period assignment

## Snapshot versioning

**Immutability:**

- `metric_snapshots` are immutable once created
- Identical inputs produce identical snapshot via unique index
- Regeneration creates new version if inputs differ

**Snapshot contents:**

- `client_id`, `metric_key`, `attribution_level`
- `period_start`, `period_end` in client timezone
- `value`, `numerator`, `denominator`
- `unit`, `currency`
- `formula_version`, `input_cutoff_at`
- `quality_status`, `quality_reasons`
- `source_entity_id`, `entity_display_name` for non-client levels

**Quality status:**

- `verified`: All inputs present, no quality issues
- `partial`: Some inputs missing, proceed with caution
- `unavailable`: Critical inputs missing, value is null

**Deterministic regeneration:**

Same `(client_id, metric_key, period_start, period_end, attribution_level, source_entity_id, formula_version, input_cutoff_at)` produces the same snapshot via database constraint.

## Period comparison

**Default comparison:**

- Current period: specified `[start, end)`
- Previous period: equal-length period immediately before `[start - duration, start)`
- Duration = `period_end - period_start`

**Metrics calculated:**

- `value`: Current period value
- `previous_value`: Previous period value
- `absolute_change`: `value - previous_value` (null if either unavailable)
- `percentage_change`: `(value - previous_value) / abs(previous_value) * 100` (null if previous is zero or unavailable)

**KPI comparison:**

- `target_value`: From `client_kpis.target_value`
- `variance`: `value - target_value` (null if no target)
- `on_target`: Derived from KPI `direction`:
  - `increase`: `value >= target_value`
  - `decrease`: `value <= target_value`
  - `range`: `value` within approved tolerance

## API routes

All routes require `client_id` in the path.

| Method | Route | Purpose |
|---|---|---|
| `POST` | `/api/v1/clients/{client_id}/normalize` | Run normalisation |
| `POST` | `/api/v1/clients/{client_id}/match` | Run matching |
| `GET` | `/api/v1/clients/{client_id}/leads/unmatched` | List unmatched leads |
| `GET` | `/api/v1/clients/{client_id}/leads/ambiguous` | List ambiguous leads |
| `GET` | `/api/v1/clients/{client_id}/leads/duplicates` | List duplicate leads |
| `POST` | `/api/v1/clients/{client_id}/leads/{lead_id}/match` | Submit manual match |
| `GET` | `/api/v1/clients/{client_id}/metrics` | Preview metrics for period |
| `POST` | `/api/v1/clients/{client_id}/snapshots` | Generate frozen snapshot |
| `GET` | `/api/v1/clients/{client_id}/snapshots` | List snapshots |
| `GET` | `/api/v1/clients/{client_id}/snapshots/{snapshot_id}` | Retrieve one snapshot |

## UI routes

| Route | Purpose |
|---|---|
| `/clients/[clientId]/matching` | Unmatched/ambiguous review and manual matching |
| `/clients/[clientId]/metrics` | Metrics dashboard with snapshot generation |

## Two-client test coverage

De-identified fixtures cover:

- Different Sheet column mappings per client
- Different source status values per client
- Exact ID matches (ad, ad-set, campaign)
- UTM matches
- Unique name matches
- Ambiguous name records (remain unmatched)
- Unmatched records
- Duplicate source rows
- Qualified, disqualified, invalid, and converted statuses
- Zero-denominator edge cases
- Previous-period data for comparison

**Isolation verification:**

- Client A leads never appear in Client B queries
- Client A matches never reference Client B entities
- Client A metrics never include Client B data
- Cross-client identifiers are not matched

## Prototype limitations

- No live pilot data validated
- No fuzzy name matching
- No bulk manual match actions
- No scheduled metric generation
- Limited pagination (capped at 1000)
- No PDF export
- No GLM narrative generation
- Basic UI without advanced charts

## Deferred for later

- Live pilot reconciliation
- Advanced manual review filters
- Bulk match approval/rejection
- Export to CSV/Excel
- Performance optimisation for large volumes
- Scheduled snapshot generation
- Advanced anomaly detection
- Comprehensive accessibility audit
- UI polish

## Validation

Run before commit:

- API Ruff format and lint
- API pytest (63+ tests)
- Web lint and typecheck
- Web production build
- Shared-types typecheck
- Migration validation against disposable PostgreSQL 17

## Audit trail

All normalisation, matching, and snapshot operations create `audit_events` records with:

- `client_id`
- `action`: `normalize`, `match`, `manual_match`, `snapshot`
- `entity_type`: `lead_record`, `lead_match`, `metric_snapshot`
- `entity_id`
- `event_metadata`: Relevant non-PII details
- `occurred_at`
