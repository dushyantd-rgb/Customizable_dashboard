# Phase 3 connector prototype

Phase 3 adds client-scoped, manually triggered Meta Ads and Google Sheets connectors. It stays
within the trusted local MVP: there is no application authentication, scheduler, Phase 4 metrics,
report generation, or Google Sheet write path.

## Delivered flow

- Meta uses one backend environment token to discover accounts. Each reporting client can select
  one account, test it, sync a bounded date range, and inspect sync history.
- Meta stores client-owned accounts, campaigns, ad sets, ads, and daily insights with stable
  external identifiers and conflict keys.
- Google OAuth uses an expiring, HMAC-signed state bound to the reporting `client_id`. Access and
  refresh tokens are encrypted with AES-256-GCM before database persistence and never returned to
  the browser.
- Each reporting client can select one spreadsheet and worksheet, preview headers and three sample
  rows, configure approved column and lead-status mappings, test the configuration, run a manual
  read-only sync, and inspect sync history.
- Sheet rows retain raw values and source lineage. An unchanged source-row version is stored once;
  later sync runs count it as skipped.

## Safety boundaries

- Every owned API route carries `client_id` in the path, and every repository lookup or mutation is
  filtered by `client_id`.
- Composite foreign keys preserve same-client parent relationships.
- Meta credentials remain environment-only. Google credentials use backend-only encrypted storage.
- Provider and unexpected failures use the shared safe-error response contract. Sync-run summaries
  contain fixed safe text rather than provider payloads or credentials.
- Google requests use only `spreadsheets.readonly` and `drive.metadata.readonly`; the connector HTTP
  client performs GET requests only.
- Placeholder environment values are normalized to unconfigured state.

## Prototype limits

- Live Meta and Google flows require operator-supplied credentials and were not exercised in this
  credential-free workspace.
- Meta pagination and Google row pagination are intentionally bounded for the prototype.
- OAuth state is tamper-evident and short-lived but not persisted as a one-time nonce.
- Sync is manual only. Mapping drives validation and raw ingestion; canonical lead materialization is
  deferred to Phase 4.

## Validation

Mocked connector tests cover encryption, OAuth tampering and expiry, client isolation, approved
mappings, missing required columns, idempotent ingestion, safe sync-run failure state, and the
read-only Google transport. The regular API and web suites cover the route-wired management UI and
shared safe-error behavior.
