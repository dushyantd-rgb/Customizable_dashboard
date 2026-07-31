# Database discovery evidence

Phase 0 used read-only inspection of the available legacy repository at `D:\growthbyte\seobyte\SEOByte` (commit observed: `27c9d7f35ca9f8936adc5ec1befde49c172f6882`, with pre-existing uncommitted changes).

Reviewed evidence included:

- `supabase/migrations/*.sql` through `20260729150000_org_meta_credentials.sql`
- relevant API models under `apps/api/app/models/`
- Meta/lead sync definitions under `apps/api/app/sync/`
- reporting query/types under `apps/web/lib/insights/`

No SQL was executed against a database. No schema dump or database connection was supplied, so migration files—not live catalog state—are the source of record for this discovery output.
