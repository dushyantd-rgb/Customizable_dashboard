# Phase 0 sign-off checklist

Overall status: **Documentation complete, evidence sign-off blocked**.

## Documentation and boundary

- [x] Standalone documentation-only project shell created.
- [x] Available legacy migrations and relevant models inspected read-only.
- [x] Legacy schema findings documented with live-state caveats.
- [x] Source-to-target proposal documented.
- [x] Canonical, lead-status, attribution, metric, and security contracts documented.
- [x] Missing evidence recorded rather than invented.
- [x] Root `.env.example` present and inspected with values redacted.
- [x] Confirmed credential inventory documented; extra placeholders are not treated as available credentials.
- [x] No feature code, OAuth flow, ingestion, runtime knowledge connection, production migration, or data copy added.
- [ ] Latest `GrowthByte_Reporting_Platform_TRD.md` supplied at the project root and reconciled.

## Confirmed MVP security scope

- [x] MVP has no application login, authentication, authorization, users, memberships, roles, or permission matrix.
- [x] MVP is restricted to local or trusted-private-network operation.
- [x] Public deployment is prohibited until later authentication and authorization work is complete.
- [x] RLS-based user authorization is deferred and is not a Phase 0 blocker.
- [x] Supabase service-role credentials and all confirmed secrets are backend-only and prohibited from browser delivery.
- [x] Google OAuth is documented solely as a future Google Sheets connection, not application login.
- [x] Existing knowledge Supabase is limited to read-only Phase 0 inspection with no runtime connection, migration, or copy.

## Client-scoping and no-data-mixing acceptance

- [x] Every proposed client-owned target entity contains non-null `client_id`.
- [x] Source account/Sheet identifiers require an explicit client mapping; names and legacy account keys are not authority.
- [x] Same-client parent/child FK and backend-validation requirements are documented.
- [x] Ingestion, normalization, attribution, metrics, reports, exports, caches, agent context, and MCP context are each bound to one `client_id`.
- [x] Missing/conflicting/mixed client identifiers must fail before business-data reads or writes.
- [x] Cross-client collision fixtures and no-data-mixing test cases are defined as later implementation acceptance criteria.
- [x] User/RLS policy-matrix approval is not included in the Phase 0 exit gate.

## Evidence and stakeholder approvals still required

- [ ] Source-to-target schema approved after missing evidence is incorporated.
- [ ] Knowledge model and migration strategy approved.
- [ ] Canonical data contract approved.
- [ ] Two pilot clients explicitly selected.
- [ ] Two pilot Sheet samples inspected and mappings approved.
- [ ] Attribution feasibility confirmed for each pilot.
- [ ] Pilot Meta fields, action definitions, account permissions, and API version confirmed.
- [ ] Lead-status, duplicate, reviewed-lead, and converted/qualified rules approved.
- [ ] Metric formulas, cohort rules, timezone, currency, missing-data, and comparison rules approved.
- [ ] PII, retention, logging, GLM data handling, and trusted-network operating controls approved.

## Exit rule

Phase 0 cannot be signed off while the TRD, pilot Sheet evidence, pilot Meta field inventory, lead-status decisions, or knowledge migration strategy remain unresolved. Once those evidence items are supplied and the resulting contracts are approved, stop and request explicit authorization before any Phase 1 work.

