-- GrowthByte Reporting Platform
-- SuperK Franchise: client-locked monthly Meta, GSC, lead-import, and snapshot lineage.

begin;

alter table public.sync_runs
  add column if not exists vertical text,
  add column if not exists source_identifier text,
  add column if not exists source_version text,
  add column if not exists source_hash text,
  add column if not exists warnings jsonb not null default '[]'::jsonb;

alter table public.google_oauth_credentials
  add column if not exists granted_scopes jsonb not null default '[]'::jsonb;

alter table public.meta_accounts
  add column if not exists vertical text not null default 'legacy';
alter table public.meta_campaigns
  add column if not exists vertical text not null default 'legacy';
alter table public.meta_ad_sets
  add column if not exists vertical text not null default 'legacy';
alter table public.meta_ads
  add column if not exists vertical text not null default 'legacy';
alter table public.meta_daily_insights
  add column if not exists vertical text not null default 'legacy',
  add column if not exists link_clicks bigint;

alter table public.meta_accounts
  drop constraint if exists meta_accounts_one_per_client;

create unique index if not exists meta_accounts_client_vertical_unique
  on public.meta_accounts (client_id, vertical);

create index if not exists meta_daily_insights_client_vertical_date_idx
  on public.meta_daily_insights (client_id, vertical, report_date desc);

create table if not exists public.meta_period_insights (
  id uuid primary key default gen_random_uuid(),
  client_id uuid not null,
  vertical text not null,
  meta_account_id uuid not null,
  sync_run_id uuid,
  period_start date not null,
  period_end date not null,
  entity_level text not null,
  external_entity_id text not null,
  entity_display_name text,
  spend numeric(20,6),
  currency character(3),
  impressions bigint,
  reach bigint,
  link_clicks bigint,
  meta_reported_leads bigint,
  raw_metrics jsonb not null default '{}'::jsonb,
  source_hash text not null,
  synced_at timestamptz not null default now(),
  created_at timestamptz not null default now(),
  constraint meta_period_insights_client_fk
    foreign key (client_id) references public.clients (id),
  constraint meta_period_insights_account_fk
    foreign key (client_id, meta_account_id)
    references public.meta_accounts (client_id, id),
  constraint meta_period_insights_sync_fk
    foreign key (client_id, sync_run_id)
    references public.sync_runs (client_id, id),
  constraint meta_period_insights_client_id_id_unique unique (client_id, id),
  constraint meta_period_insights_period_order check (period_end >= period_start),
  constraint meta_period_insights_vertical_nonempty check (btrim(vertical) <> ''),
  constraint meta_period_insights_source_hash_nonempty check (btrim(source_hash) <> ''),
  constraint meta_period_insights_entity_level_check check (
    entity_level = 'account'
    or entity_level = 'campaign'
    or entity_level = 'ad_set'
    or entity_level = 'ad'
  ),
  constraint meta_period_insights_counts_nonnegative check (
    (impressions is null or impressions >= 0)
    and (reach is null or reach >= 0)
    and (link_clicks is null or link_clicks >= 0)
    and (meta_reported_leads is null or meta_reported_leads >= 0)
  ),
  constraint meta_period_insights_source_unique unique (
    client_id,
    vertical,
    meta_account_id,
    period_start,
    period_end,
    entity_level,
    external_entity_id,
    source_hash
  )
);

create index if not exists meta_period_insights_client_period_idx
  on public.meta_period_insights (client_id, vertical, period_start, period_end);

create table if not exists public.lead_json_imports (
  id uuid primary key default gen_random_uuid(),
  client_id uuid not null,
  vertical text not null,
  source_identifier text not null,
  source_version integer not null,
  report_month date not null,
  payload_hash text not null,
  schema_version text not null,
  total_leads bigint not null,
  rtm_leads bigint not null,
  comment text,
  mapping_preview jsonb not null default '{}'::jsonb,
  import_status text not null,
  imported_at timestamptz,
  created_at timestamptz not null default now(),
  constraint lead_json_imports_client_fk
    foreign key (client_id) references public.clients (id),
  constraint lead_json_imports_client_id_id_unique unique (client_id, id),
  constraint lead_json_imports_source_version_unique unique (
    client_id, vertical, source_identifier, source_version
  ),
  constraint lead_json_imports_payload_unique unique (
    client_id, vertical, source_identifier, payload_hash
  ),
  constraint lead_json_imports_vertical_nonempty check (btrim(vertical) <> ''),
  constraint lead_json_imports_source_nonempty check (btrim(source_identifier) <> ''),
  constraint lead_json_imports_hash_nonempty check (btrim(payload_hash) <> ''),
  constraint lead_json_imports_version_positive check (source_version >= 1),
  constraint lead_json_imports_counts_valid check (
    total_leads >= 0 and rtm_leads >= 0 and rtm_leads <= total_leads
  ),
  constraint lead_json_imports_month_first check (
    report_month = date_trunc('month', report_month)::date
  )
);

create index if not exists lead_json_imports_client_month_idx
  on public.lead_json_imports (client_id, vertical, report_month, source_version desc);

create table if not exists public.gsc_properties (
  id uuid primary key default gen_random_uuid(),
  client_id uuid not null,
  vertical text not null,
  integration_connection_id uuid not null,
  site_url text not null,
  permission_level text,
  connection_status text not null,
  last_verified_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint gsc_properties_client_fk
    foreign key (client_id) references public.clients (id),
  constraint gsc_properties_connection_fk
    foreign key (client_id, integration_connection_id)
    references public.integration_connections (client_id, id),
  constraint gsc_properties_client_id_id_unique unique (client_id, id),
  constraint gsc_properties_client_vertical_unique unique (client_id, vertical),
  constraint gsc_properties_site_unique unique (client_id, vertical, site_url),
  constraint gsc_properties_vertical_nonempty check (btrim(vertical) <> ''),
  constraint gsc_properties_site_nonempty check (btrim(site_url) <> '')
);

create index if not exists gsc_properties_client_status_idx
  on public.gsc_properties (client_id, vertical, connection_status);

drop trigger if exists gsc_properties_set_updated_at on public.gsc_properties;
create trigger gsc_properties_set_updated_at
before update on public.gsc_properties
for each row execute function public.set_growthbyte_updated_at();

create table if not exists public.gsc_period_totals (
  id uuid primary key default gen_random_uuid(),
  client_id uuid not null,
  vertical text not null,
  gsc_property_id uuid not null,
  sync_run_id uuid,
  period_start date not null,
  period_end date not null,
  clicks numeric(20,6),
  impressions numeric(20,6),
  ctr numeric(20,12),
  average_position numeric(20,6),
  response_aggregation_type text,
  data_state text,
  source_hash text not null,
  synced_at timestamptz not null default now(),
  created_at timestamptz not null default now(),
  constraint gsc_period_totals_client_fk
    foreign key (client_id) references public.clients (id),
  constraint gsc_period_totals_property_fk
    foreign key (client_id, gsc_property_id)
    references public.gsc_properties (client_id, id),
  constraint gsc_period_totals_sync_fk
    foreign key (client_id, sync_run_id)
    references public.sync_runs (client_id, id),
  constraint gsc_period_totals_client_id_id_unique unique (client_id, id),
  constraint gsc_period_totals_period_order check (period_end >= period_start),
  constraint gsc_period_totals_source_hash_nonempty check (btrim(source_hash) <> ''),
  constraint gsc_period_totals_nonnegative check (
    (clicks is null or clicks >= 0)
    and (impressions is null or impressions >= 0)
    and (ctr is null or ctr >= 0)
    and (average_position is null or average_position >= 0)
  ),
  constraint gsc_period_totals_source_unique unique (
    client_id, vertical, gsc_property_id, period_start, period_end, source_hash
  )
);

create index if not exists gsc_period_totals_client_period_idx
  on public.gsc_period_totals (client_id, vertical, period_start, period_end);

create table if not exists public.gsc_dimension_metrics (
  id uuid primary key default gen_random_uuid(),
  client_id uuid not null,
  vertical text not null,
  gsc_property_id uuid not null,
  sync_run_id uuid,
  period_start date not null,
  period_end date not null,
  dimension_type text not null,
  dimension_value text not null,
  clicks numeric(20,6),
  impressions numeric(20,6),
  ctr numeric(20,12),
  average_position numeric(20,6),
  source_hash text not null,
  synced_at timestamptz not null default now(),
  created_at timestamptz not null default now(),
  constraint gsc_dimension_metrics_client_fk
    foreign key (client_id) references public.clients (id),
  constraint gsc_dimension_metrics_property_fk
    foreign key (client_id, gsc_property_id)
    references public.gsc_properties (client_id, id),
  constraint gsc_dimension_metrics_sync_fk
    foreign key (client_id, sync_run_id)
    references public.sync_runs (client_id, id),
  constraint gsc_dimension_metrics_client_id_id_unique unique (client_id, id),
  constraint gsc_dimension_metrics_period_order check (period_end >= period_start),
  constraint gsc_dimension_metrics_dimension_check check (
    dimension_type = 'query' or dimension_type = 'page'
  ),
  constraint gsc_dimension_metrics_value_nonempty check (btrim(dimension_value) <> ''),
  constraint gsc_dimension_metrics_source_hash_nonempty check (btrim(source_hash) <> ''),
  constraint gsc_dimension_metrics_source_unique unique (
    client_id,
    vertical,
    gsc_property_id,
    period_start,
    period_end,
    dimension_type,
    dimension_value,
    source_hash
  )
);

create index if not exists gsc_dimension_metrics_client_period_idx
  on public.gsc_dimension_metrics (
    client_id, vertical, period_start, period_end, dimension_type
  );

create table if not exists public.monthly_report_snapshots (
  id uuid primary key default gen_random_uuid(),
  client_id uuid not null,
  vertical text not null,
  report_month date not null,
  snapshot_version integer not null,
  formula_version text not null,
  input_cutoff_at timestamptz not null,
  input_hash text not null,
  meta_sync_run_id uuid,
  gsc_sync_run_id uuid,
  lead_json_import_id uuid,
  knowledge_references jsonb not null default '[]'::jsonb,
  knowledge_hash text not null,
  kpi_references jsonb not null default '[]'::jsonb,
  kpi_hash text not null,
  quality_status text not null,
  quality_reasons jsonb not null default '[]'::jsonb,
  finalized_at timestamptz not null default now(),
  created_at timestamptz not null default now(),
  constraint monthly_report_snapshots_client_fk
    foreign key (client_id) references public.clients (id),
  constraint monthly_report_snapshots_meta_sync_fk
    foreign key (client_id, meta_sync_run_id)
    references public.sync_runs (client_id, id),
  constraint monthly_report_snapshots_gsc_sync_fk
    foreign key (client_id, gsc_sync_run_id)
    references public.sync_runs (client_id, id),
  constraint monthly_report_snapshots_lead_import_fk
    foreign key (client_id, lead_json_import_id)
    references public.lead_json_imports (client_id, id),
  constraint monthly_report_snapshots_client_id_id_unique unique (client_id, id),
  constraint monthly_report_snapshots_version_unique unique (
    client_id, vertical, report_month, formula_version, snapshot_version
  ),
  constraint monthly_report_snapshots_input_unique unique (
    client_id, vertical, report_month, formula_version, input_hash
  ),
  constraint monthly_report_snapshots_month_first check (
    report_month = date_trunc('month', report_month)::date
  ),
  constraint monthly_report_snapshots_version_positive check (snapshot_version >= 1),
  constraint monthly_report_snapshots_hashes_nonempty check (
    btrim(input_hash) <> ''
    and btrim(knowledge_hash) <> ''
    and btrim(kpi_hash) <> ''
  )
);

create index if not exists monthly_report_snapshots_client_month_idx
  on public.monthly_report_snapshots (
    client_id, vertical, report_month desc, snapshot_version desc
  );

alter table public.metric_snapshots
  add column if not exists monthly_snapshot_id uuid,
  add column if not exists vertical text,
  add column if not exists previous_value numeric,
  add column if not exists absolute_change numeric,
  add column if not exists percentage_change numeric,
  add column if not exists kpi_target numeric;

alter table public.metric_snapshots
  drop constraint if exists metric_snapshots_monthly_snapshot_fk;
alter table public.metric_snapshots
  add constraint metric_snapshots_monthly_snapshot_fk
  foreign key (client_id, monthly_snapshot_id)
  references public.monthly_report_snapshots (client_id, id);

create unique index if not exists metric_snapshots_monthly_metric_unique
  on public.metric_snapshots (
    client_id,
    monthly_snapshot_id,
    metric_key,
    attribution_level,
    coalesce(source_entity_id, '')
  )
  where monthly_snapshot_id is not null;

create index if not exists metric_snapshots_client_monthly_idx
  on public.metric_snapshots (client_id, monthly_snapshot_id, metric_key);

alter table public.reports
  add column if not exists vertical text,
  add column if not exists monthly_snapshot_id uuid;

alter table public.reports
  drop constraint if exists reports_monthly_snapshot_fk;
alter table public.reports
  add constraint reports_monthly_snapshot_fk
  foreign key (client_id, monthly_snapshot_id)
  references public.monthly_report_snapshots (client_id, id);

create index if not exists reports_client_monthly_snapshot_idx
  on public.reports (client_id, monthly_snapshot_id)
  where monthly_snapshot_id is not null;

alter table public.report_versions
  add column if not exists monthly_snapshot_id uuid,
  add column if not exists agent_run_id uuid;

alter table public.report_versions
  drop constraint if exists report_versions_monthly_snapshot_fk;
alter table public.report_versions
  add constraint report_versions_monthly_snapshot_fk
  foreign key (client_id, monthly_snapshot_id)
  references public.monthly_report_snapshots (client_id, id);

create index if not exists report_versions_client_monthly_snapshot_idx
  on public.report_versions (client_id, monthly_snapshot_id)
  where monthly_snapshot_id is not null;

create or replace function public.prevent_finalized_monthly_snapshot_mutation()
returns trigger
language plpgsql
as $$
begin
  raise exception 'Finalized monthly report snapshots are immutable';
end;
$$;

drop trigger if exists monthly_report_snapshots_immutable
  on public.monthly_report_snapshots;
create trigger monthly_report_snapshots_immutable
before update or delete on public.monthly_report_snapshots
for each row execute function public.prevent_finalized_monthly_snapshot_mutation();

create or replace function public.prevent_monthly_metric_mutation()
returns trigger
language plpgsql
as $$
begin
  if old.monthly_snapshot_id is not null then
    raise exception 'Monthly snapshot metrics are immutable';
  end if;
  if tg_op = 'DELETE' then
    return old;
  end if;
  return new;
end;
$$;

drop trigger if exists metric_snapshots_monthly_immutable
  on public.metric_snapshots;
create trigger metric_snapshots_monthly_immutable
before update or delete on public.metric_snapshots
for each row execute function public.prevent_monthly_metric_mutation();

create or replace function public.prevent_approved_report_version_mutation()
returns trigger
language plpgsql
as $$
begin
  if old.status = 'approved' then
    raise exception 'Approved report versions are immutable';
  end if;
  if tg_op = 'DELETE' then
    return old;
  end if;
  return new;
end;
$$;

drop trigger if exists report_versions_approved_immutable
  on public.report_versions;
create trigger report_versions_approved_immutable
before update or delete on public.report_versions
for each row execute function public.prevent_approved_report_version_mutation();

commit;
