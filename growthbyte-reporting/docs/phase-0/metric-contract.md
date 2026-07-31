# Metric contract

Status: **deterministic formula proposal; business semantics and pilot data require approval**.

All published values are computed in versioned SQL or Python. A GLM may explain stored verified snapshots but may not calculate, modify, infer, or “repair” a metric. `NULL/unavailable` is distinct from zero.

## Formula matrix

| Metric | Numerator | Denominator | Proposed formula |
|---|---|---|---|
| Cost per lead (CPL) | Meta spend at the chosen scope | Meta-reported leads at the same scope | `spend / meta_leads` |
| Qualification rate | Reviewed leads in `qualified` plus `converted` if the approved funnel says converted implies qualified | All reviewed leads | `qualified_outcomes / reviewed_leads * 100` |
| Cost per qualified lead (CPQL) | Meta spend at the supported attributed scope | Sheet-qualified leads attributed to that same scope | `spend / attributed_qualified_leads` |
| Invalid lead rate | Reviewed leads mapped to `invalid` | All reviewed leads | `invalid_leads / reviewed_leads * 100` |
| Conversion rate | Converted leads | Qualified cohort (`qualified + converted`) under approved funnel semantics | `converted_leads / qualified_cohort * 100` |
| Review coverage | Reviewed, valid normalized leads | Eligible normalized leads after only approved technical exclusions | `reviewed_leads / eligible_leads * 100` |

Qualification and conversion formulas remain blocked until the converted/qualified relationship is approved. “Eligible” exclusions (test rows, confirmed duplicates, corrupt rows) must be enumerated; business outcomes such as invalid/disqualified are not silently excluded.

## Common behavior

- **Data source:** spend/delivery/Meta leads come from `meta_daily_performance`; business outcomes come from versioned `normalised_leads`; joins use approved `lead_attribution`; coverage uses normalized lead QA state.
- **Attribution level:** CPL can exist wherever Meta provides compatible spend/leads. CPQL and status rates exist only at levels supported by lead attribution. Client-level data never implies campaign/creative metrics.
- **Timezone:** Meta facts use the Meta account reporting day. Sheet event timestamps are parsed in the configured source timezone. Report periods are constructed in `clients.reporting_timezone`; inclusions use a half-open interval `[start,end)`. Cross-timezone reconciliation is explicit.
- **Currency:** calculate monetary metrics only within one ISO currency. If multiple accounts/currencies occur, publish separate values unless an approved dated FX source/method exists. Never sum or compare unlabeled mixed currencies.
- **Zero denominator:** return `NULL` with reason `zero_denominator`; never show zero or infinity. The numerator remains stored for QA.
- **Missing data:** return `NULL`/`partial` with machine-readable reasons. Missing outcomes are not zero; unknown statuses are not reviewed. Suppress levels with incomplete attribution.
- **Late data:** snapshots record input cutoff and formula/mapping/attribution versions. Recalculation creates a new snapshot/report version.
- **Rounding:** retain database precision; round only for display according to an approved unit rule.

## Metric-specific edge cases

### CPL

- Use Meta action definitions versioned by the ingestion code; the legacy source’s lead action set is evidence, not automatically the target standard.
- Meta spend > 0 with zero leads produces unavailable CPL plus `zero_denominator`.
- Do not replace Meta lead count with Sheet row count under the same metric name; a separate “cost per Sheet lead” would need approval.

### Qualification rate

- The proposed denominator is reviewed leads so incomplete review is exposed separately through review coverage.
- Unmapped/blank statuses do not enter numerator or denominator.
- If the business instead wants all eligible leads as denominator, that is a separate formula version and label.

### CPQL

- Spend and qualified lead must share client, account, reporting period, attribution level, and supported entity.
- Unmatched/client-only leads do not enter lower-level denominators.
- Do not allocate account spend to leads by ratio unless a business-approved allocation metric is separately defined.

### Invalid lead rate

- Only canonical `invalid` enters the numerator; `disqualified` is not invalid.
- Confirmed duplicate handling is blocked by the status contract.

### Conversion rate

- Proposed denominator is the qualified cohort; lead-to-conversion rate using all eligible leads would be a separately named metric.
- Use one approved cohort/as-of method. Created-period cohorts and conversions-occurring-in-period must not be mixed.

### Review coverage

- Rows rejected for technical parse errors are reported separately, not hidden from sync QA.
- A sync or automation attempt alone does not mark a lead reviewed.

## Period comparison

Default proposal: compare with the immediately preceding equal-duration period using the same client timezone, filters, formula version, currency, and attribution scope.

- Absolute delta: `current - previous` when both values are available.
- Percentage change: `(current - previous) / abs(previous) * 100`.
- Previous zero: percentage change is unavailable with reason `zero_previous`; show absolute change.
- Missing/partial prior data: comparison unavailable, not zero.
- Rate metrics show both percentage-point change and, optionally, relative change; labels must distinguish them.
- Favorability is derived from the KPI direction, not assumed from the sign (lower CPL/invalid rate may be favorable).

