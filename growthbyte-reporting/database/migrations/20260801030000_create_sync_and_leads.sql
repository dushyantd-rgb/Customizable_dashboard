-- GrowthByte Reporting Platform
-- Phase 2: sync lineage, raw Sheet evidence, normalized leads, and matches.

begin;

create table if not exists public.sync_runs (
  id uuid primary key default gen_random_uuid(),
  client_id uuid not null,
  integration_connection_id uuid,
  google_sheet_config_id uuid,
  source_type text not null,
  status text not null,
  started_at timestamptz,
  finished_at timestamptz,
  watermark_from timestamptz,
  watermark_to timestamptz,
  rows_read bigint not null default 0,
  rows_written bigint not null default 0,
  rows_rejected bigint not null default 0,
  error_code text,
  error_summary text,
  initiated_by_label text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint sync_runs_client_fk
    foreign key (client_id) references public.clients (id),
  constraint sync_runs_connection_fk
    foreign key (client_id, integration_connection_id)
    references public.integration_connections (client_id, id),
  constraint sync_runs_sheet_config_fk
    foreign key (client_id, google_sheet_config_id)
    references public.google_sheet_configs (client_id, id),
  constraint sync_runs_client_id_id_unique unique (client_id, id),
  constraint sync_runs_source_type_nonempty check (btrim(source_type) <> ''),
  constraint sync_runs_status_nonempty check (btrim(status) <> ''),
  constraint sync_runs_time_order check (
    finished_at is null or started_at is null or finished_at >= started_at
  ),
  constraint sync_runs_watermark_order check (
    watermark_from is null or watermark_to is null or watermark_to >= watermark_from
  ),
  constraint sync_runs_rows_nonnegative check (
    rows_read >= 0 and rows_written >= 0 and rows_rejected >= 0
  )
);

create index if not exists sync_runs_client_source_created_idx
  on public.sync_runs (client_id, source_type, created_at desc);

create index if not exists sync_runs_client_status_idx
  on public.sync_runs (client_id, status, created_at desc);

create index if not exists sync_runs_sheet_config_idx
  on public.sync_runs (client_id, google_sheet_config_id, created_at desc)
  where google_sheet_config_id is not null;

create index if not exists sync_runs_connection_idx
  on public.sync_runs (client_id, integration_connection_id, created_at desc)
  where integration_connection_id is not null;

drop trigger if exists sync_runs_set_updated_at on public.sync_runs;
create trigger sync_runs_set_updated_at
before update on public.sync_runs
for each row execute function public.set_growthbyte_updated_at();

create table if not exists public.raw_sheet_rows (
  id uuid primary key default gen_random_uuid(),
  client_id uuid not null,
  google_sheet_config_id uuid not null,
  sync_run_id uuid not null,
  worksheet_name text not null,
  row_number integer not null,
  source_row_key text not null,
  raw_values jsonb not null,
  row_hash text not null,
  observed_at timestamptz not null,
  is_deleted_at_source boolean not null default false,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint raw_sheet_rows_client_fk
    foreign key (client_id) references public.clients (id),
  constraint raw_sheet_rows_config_fk
    foreign key (client_id, google_sheet_config_id)
    references public.google_sheet_configs (client_id, id),
  constraint raw_sheet_rows_sync_run_fk
    foreign key (client_id, sync_run_id)
    references public.sync_runs (client_id, id),
  constraint raw_sheet_rows_client_id_id_unique unique (client_id, id),
  constraint raw_sheet_rows_run_source_unique
    unique (client_id, sync_run_id, source_row_key),
  constraint raw_sheet_rows_worksheet_name_nonempty check (btrim(worksheet_name) <> ''),
  constraint raw_sheet_rows_row_number_positive check (row_number >= 1),
  constraint raw_sheet_rows_source_row_key_nonempty check (btrim(source_row_key) <> ''),
  constraint raw_sheet_rows_row_hash_nonempty check (btrim(row_hash) <> '')
);

create index if not exists raw_sheet_rows_config_source_idx
  on public.raw_sheet_rows (client_id, google_sheet_config_id, source_row_key);

create index if not exists raw_sheet_rows_sync_run_idx
  on public.raw_sheet_rows (client_id, sync_run_id);

drop trigger if exists raw_sheet_rows_set_updated_at on public.raw_sheet_rows;
create trigger raw_sheet_rows_set_updated_at
before update on public.raw_sheet_rows
for each row execute function public.set_growthbyte_updated_at();

create table if not exists public.lead_records (
  id uuid primary key default gen_random_uuid(),
  client_id uuid not null,
  raw_sheet_row_id uuid not null,
  source_lead_id text,
  meta_lead_id text,
  lead_at timestamptz,
  source_status_raw text,
  canonical_status text not null,
  is_reviewed boolean not null,
  qualification_at timestamptz,
  conversion_at timestamptz,
  mapping_version integer not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint lead_records_client_fk
    foreign key (client_id) references public.clients (id),
  constraint lead_records_raw_row_fk
    foreign key (client_id, raw_sheet_row_id)
    references public.raw_sheet_rows (client_id, id),
  constraint lead_records_client_id_id_unique unique (client_id, id),
  constraint lead_records_raw_mapping_unique
    unique (client_id, raw_sheet_row_id, mapping_version),
  constraint lead_records_canonical_status_nonempty check (btrim(canonical_status) <> ''),
  constraint lead_records_mapping_version_positive check (mapping_version >= 1),
  constraint lead_records_qualification_time check (
    qualification_at is null or lead_at is null or qualification_at >= lead_at
  ),
  constraint lead_records_conversion_time check (
    conversion_at is null or lead_at is null or conversion_at >= lead_at
  )
);

create index if not exists lead_records_client_lead_at_idx
  on public.lead_records (client_id, lead_at desc);

create index if not exists lead_records_client_status_idx
  on public.lead_records (client_id, canonical_status, is_reviewed);

create index if not exists lead_records_source_lead_idx
  on public.lead_records (client_id, source_lead_id)
  where source_lead_id is not null;

create index if not exists lead_records_meta_lead_idx
  on public.lead_records (client_id, meta_lead_id)
  where meta_lead_id is not null;

drop trigger if exists lead_records_set_updated_at on public.lead_records;
create trigger lead_records_set_updated_at
before update on public.lead_records
for each row execute function public.set_growthbyte_updated_at();

create table if not exists public.lead_matches (
  id uuid primary key default gen_random_uuid(),
  client_id uuid not null,
  lead_record_id uuid not null,
  integration_connection_id uuid,
  external_account_id text,
  account_display_name text,
  external_campaign_id text,
  campaign_display_name text,
  external_ad_set_id text,
  ad_set_display_name text,
  external_ad_id text,
  ad_display_name text,
  method text not null,
  confidence numeric(5,4),
  matched_identifiers jsonb not null default '{}'::jsonb,
  rule_version text not null,
  review_status text not null,
  reviewed_by_label text,
  reviewed_at timestamptz,
  is_active boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint lead_matches_client_fk
    foreign key (client_id) references public.clients (id),
  constraint lead_matches_lead_record_fk
    foreign key (client_id, lead_record_id)
    references public.lead_records (client_id, id),
  constraint lead_matches_connection_fk
    foreign key (client_id, integration_connection_id)
    references public.integration_connections (client_id, id),
  constraint lead_matches_client_id_id_unique unique (client_id, id),
  constraint lead_matches_method_nonempty check (btrim(method) <> ''),
  constraint lead_matches_confidence_range check (
    confidence is null or (confidence >= 0 and confidence <= 1)
  ),
  constraint lead_matches_rule_version_nonempty check (btrim(rule_version) <> ''),
  constraint lead_matches_review_status_nonempty check (btrim(review_status) <> ''),
  constraint lead_matches_review_pair check (
    (reviewed_by_label is null and reviewed_at is null)
    or (reviewed_by_label is not null and btrim(reviewed_by_label) <> '' and reviewed_at is not null)
  )
);

create unique index if not exists lead_matches_one_active_per_lead
  on public.lead_matches (client_id, lead_record_id)
  where is_active;

create index if not exists lead_matches_lead_idx
  on public.lead_matches (client_id, lead_record_id, created_at desc);

create index if not exists lead_matches_connection_idx
  on public.lead_matches (client_id, integration_connection_id, created_at desc)
  where integration_connection_id is not null;

create index if not exists lead_matches_campaign_idx
  on public.lead_matches (client_id, external_campaign_id)
  where external_campaign_id is not null;

create index if not exists lead_matches_ad_set_idx
  on public.lead_matches (client_id, external_ad_set_id)
  where external_ad_set_id is not null;

create index if not exists lead_matches_ad_idx
  on public.lead_matches (client_id, external_ad_id)
  where external_ad_id is not null;

drop trigger if exists lead_matches_set_updated_at on public.lead_matches;
create trigger lead_matches_set_updated_at
before update on public.lead_matches
for each row execute function public.set_growthbyte_updated_at();

commit;
