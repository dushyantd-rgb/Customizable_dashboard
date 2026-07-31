# Open questions and blockers

Phase 0 status: **documentation complete, evidence sign-off blocked**. Phase 1 must not start automatically.

## Sign-off blockers

| ID | Missing input / question | Evidence available | Impact | Required owner/action |
|---|---|---|---|---|
| B-001 | Latest `GrowthByte_Reporting_Platform_TRD.md` | Not found at the project root, workspace, attachment area, or surrounding GrowthByte folders | The documentation cannot be reconciled against the complete latest technical requirements | Supply the exact latest TRD at the project root |
| B-002 | Two explicitly named pilot clients and Google Sheet samples | No pilot exports/workbooks were found; legacy account names are not accepted as pilot confirmation | Columns, statuses, identifiers, formulas, PII, locale, and attribution cannot be verified | Select two pilots and provide de-identified read-only tab exports plus tab/locale/timezone metadata |
| B-003 | Pilot Meta field and permission availability | Legacy code reads campaign/day insights and ad-set targeting for fixed account keys, but target accounts/API permissions are unverified | Entity fields, daily grain, actions, identifiers, and attribution levels cannot be frozen | Provide per-pilot Meta account/permission inventory and representative field payload/schema |
| B-004 | Lead-status and funnel definitions | A legacy operational export exists, but no pilot values or approved business definitions were supplied | Status mapping and qualification/conversion formulas remain provisional | Approve per-pilot mappings, reviewed-lead rule, duplicate handling, and converted/qualified semantics |
| B-005 | Knowledge migration strategy | Legacy free-form knowledge, structured sections/versions, documents, approvals, and comments exist; the new allowed scope is unknown | Source-to-target knowledge contract and later migration validation cannot be frozen | Select knowledge sources/fields/history, provenance, exclusions, and validation approach |

## Confirmed inputs and non-blockers

- The root `.env.example` is present and was read with values redacted.
- Only reporting Supabase credentials, read-only existing knowledge Supabase credentials, Google OAuth client ID/secret, Meta access token, and GLM gateway key are confirmed as available.
- Placeholder names beyond that inventory do not establish additional available credentials.
- The MVP has no login, authentication, authorization, users, memberships, roles, or permission matrix.
- RLS-based user authorization is deferred and is **not** a Phase 0 blocker.
- Public deployment is excluded; the MVP is restricted to local or trusted-network operation.
- Existing knowledge Supabase may be inspected read-only during Phase 0, but no runtime connection, migration, or copy is approved.

## Additional open questions

- What reporting timezone and default currency applies to each pilot? Can one client have multiple Meta account currencies?
- Is qualification measured as current as-of status, a lead-created cohort, or status events occurring during the report period?
- Are converted leads always qualified? Are duplicates invalid, excluded, or independently categorized?
- What is the authoritative lead count for each report: Meta actions, unique normalized Sheet leads, or separately named measures?
- Which Meta action types count as leads and conversions for each pilot account/pixel setup?
- What UTM naming/uniqueness contract exists, and are names permitted only for reviewed lower-confidence matches?
- Which Google Sheets/Drive OAuth scopes and redirect URI are approved for the future connector? OAuth remains Sheets-only and not login.
- What raw source, lead PII, report, operational log, backup, export, and GLM trace retention periods apply?
- What GLM data-processing/retention terms are approved?
- Who performs human report review in the trusted MVP process, and how is the operator label recorded without application users?

## Evidence explicitly not inferred

- Silpa, SuperK, and every other legacy account remain unconfirmed as pilots.
- The legacy leads export is not treated as either pilot Sheet.
- Legacy `qualified_leads=0` is not treated as a business result; the source sync states Meta does not expose qualification.
- Existing legacy RLS policies are audit findings, not MVP user-authorization requirements.
- Extra `.env.example` variables are not treated as confirmed credentials or approved integrations.
- No production data, credential value, environment value, pilot field, or source mapping is fabricated.

