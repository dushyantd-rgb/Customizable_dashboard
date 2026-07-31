# Attribution feasibility

Status: **blocked — pilot Sheet samples were not supplied**.

The legacy repository refers to fixed Meta reporting account keys `silpa` and `superk`, and its leads export template contains profile name, phone, platform, DM/comment, message, automation status, response capture, qualification status, and disposition. That export is not a pilot Sheet sample and does not prove the identifiers present in either future pilot. Silpa/SuperK are therefore not silently designated as the pilots.

## Required pilot evidence

| Identifier / outcome | Pilot client 1 (not named) | Pilot client 2 (not named) |
|---|---|---|
| Meta lead ID | Not available for inspection | Not available for inspection |
| Campaign ID or name | Not available for inspection | Not available for inspection |
| Ad-set ID or name | Not available for inspection | Not available for inspection |
| Ad ID or name | Not available for inspection | Not available for inspection |
| Lead date/time | Not available for inspection | Not available for inspection |
| UTM source/medium/campaign/content/term | Not available for inspection | Not available for inspection |
| Phone or other lead identifier | Not available for inspection | Not available for inspection |
| Lead status | Not available for inspection | Not available for inspection |
| Qualification result | Not available for inspection | Not available for inspection |
| Conversion result/date | Not available for inspection | Not available for inspection |
| Current classification | **Attribution not currently possible** from supplied evidence | **Attribution not currently possible** from supplied evidence |

The classification records current evidence availability; it is not a claim that the actual Sheets lack identifiers.

## Classification rules

| Classification | Minimum compatible evidence |
|---|---|
| Exact ID attribution | Valid Meta lead/campaign/ad-set/ad identifiers that resolve within the same approved client/account |
| Reliable UTM attribution | Persisted UTMs with a unique, documented mapping to Meta entities and a compatible date/account window |
| Lower-confidence name/date attribution | Normalized entity name plus compatible account/date; ambiguity is surfaced and human approval is required |
| Client-level reporting only | The Sheet can be assigned to one client but contains no compatible campaign/creative identifiers |
| Attribution not currently possible | Client ownership or source mapping cannot be established from supplied evidence |

Phone number and lead status alone never establish a reliable Meta campaign, ad-set, or creative match. Campaign/ad names are mutable and non-unique; they support only lower-confidence matching with ambiguity checks.

## Matching order and unmatched behavior

1. Validate client/account boundary before any candidate search.
2. Attempt exact source/Meta identifier match.
3. Attempt approved UTM match with explicit uniqueness and date-window rules.
4. Optionally generate name/date candidates. Never auto-accept ambiguous or sub-threshold candidates.
5. Otherwise store `method=client_only` or `method=unmatched`; keep the lead in client totals when client ownership is known.

Unmatched leads remain visible in coverage metrics and a reconciliation queue. They are excluded from campaign/ad-set/ad-level qualification, CPQL, invalid-rate, and conversion metrics; they are never proportionally allocated or guessed. Reprocessing uses a versioned attribution rule and preserves the prior decision.

## Evidence needed to unblock

Provide read-only exports of two selected pilot tabs with headers, representative de-identified rows, timezone/locale, stable row/lead identifiers, formulas, data validation values, and any hidden lookup tabs that define statuses. Provide Meta account ids, available entity fields, permissions, and the lead-source mechanism for the same clients.

