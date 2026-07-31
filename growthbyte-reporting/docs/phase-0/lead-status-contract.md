# Lead-status contract

Status: **proposed; source values and funnel semantics require business approval**.

Canonical values are stored as machine keys (`qualified`, `in_progress`, `invalid`, `disqualified`, `converted`, `not_reviewed`) and rendered with the requested labels. Candidate source values below are examples for mapping workshops, not observations from pilot Sheets.

| Canonical label | Candidate Sheet values, subject to confirmation | Proposed meaning |
|---|---|---|
| Qualified | `qualified`, `qualified lead`, `eligible`, `good lead`, `interested` | Reviewed and meets the agreed qualification criteria; not known converted |
| In progress | `in progress`, `contacted`, `follow up`, `callback`, `pending response`, `nurturing` | Reviewed/actively worked but final qualification or disposition remains open |
| Invalid | `invalid`, `fake`, `spam`, `test`, `wrong number`, `duplicate`* | Lead record cannot be treated as a valid prospect |
| Disqualified | `disqualified`, `not eligible`, `not interested`, `out of area`, `no budget` | Valid/reviewed person or organization that fails business criteria |
| Converted | `converted`, `won`, `sale`, `customer`, `enrolled`, `booked`* | Confirmed conversion event according to a client-specific definition |
| Not reviewed | blank, `new`, `unreviewed`, `not reviewed`, unknown/unmapped values | No approved review outcome can be asserted |

`*` “duplicate,” “booked,” and similar values are business-dependent and must not be mapped until confirmed.

## Normalisation and mapping

1. Preserve the exact source cell in `source_status_raw`.
2. For lookup only, trim, Unicode-normalize, collapse whitespace, and compare case-insensitively.
3. Apply a versioned mapping scoped to the client and Sheet configuration.
4. A blank or unmapped value becomes `not_reviewed` and emits a data-quality reason. Never guess with fuzzy matching.
5. A source row containing conflicting status/qualification/conversion columns is quarantined for review or resolved by an explicitly approved precedence rule.
6. Historical normalized rows retain the mapping version used; remapping produces a new normalized version/recalculation rather than silently rewriting audited reports.

## Reviewed lead rule

Proposed: a lead is reviewed only when an approved mapping explicitly sets `counts_as_reviewed=true`. Normally `qualified`, `in_progress`, `invalid`, `disqualified`, and `converted` count as reviewed; `not_reviewed` does not. Merely opening, contacting, or synchronizing a row is not evidence of review unless the business approves that semantics.

## Converted versus qualified

Unresolved business decision. Recommended funnel semantics: `converted` is a mutually exclusive terminal status that **implies it passed qualification**, but it is not stored simultaneously as `qualified`. Under that approved rule:

- qualified-for-rate count = `qualified + converted`;
- converted count = `converted` only;
- no lead is double-counted in total/status distributions.

Until this is approved, qualification metrics that depend on converted inclusion must be `unavailable`, or published in clearly labeled alternative variants for review—not silently chosen.

## Blank, unknown, and duplicate handling

- Blank/null/whitespace: `not_reviewed`, reason `blank_status`.
- Unknown/unmapped value: `not_reviewed`, reason `unmapped_status`; add it to a mapping-review queue.
- Multiple identical source rows: retain raw evidence but select one normalized lead using an approved stable source identifier.
- Suspected duplicate people without a stable identifier: do not merge automatically. Flag for review.
- Confirmed duplicate: recommended canonical `invalid` with a separate `invalid_reason=duplicate` and `duplicate_of_lead_id`; requires approval because some clients may exclude duplicates differently.
- Status changes: retain history or source-row versions; report using the defined period/as-of rule in the metric contract.

## Decisions requiring confirmation

- Exact values used by each pilot Sheet and which column is authoritative.
- Whether `in_progress` means reviewed.
- Whether every `converted` lead necessarily qualifies, and what conversion event counts.
- Whether duplicates are invalid, excluded before status metrics, or retained in a separate category.
- Whether qualification/conversion is measured by lead-created date, status-change date, or report-as-of state.
- Client-specific invalid/disqualification reason taxonomy and precedence across multiple columns.

