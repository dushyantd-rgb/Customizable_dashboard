-- GrowthByte Reporting Platform
-- Phase 2: verified metric lineage, versioned reports, and operational audit events.

begin;

create table if not exists public.metric_snapshots (
  id uuid primary key default gen_random_uuid(),
  client_id uuid not null,
  kpi_id uuid,
  metric_key text not null,
  period_start timestamptz not null,
  period_end timestamptz not null,
  attribution_level text not null,
  source_entity_id text,
  entity_display_name text,
  value numeric,
  unit text not null,
  currency character(3),
  numerator numeric,
  denominator numeric,
  formula_version text not null,
  input_cutoff_at timestamptz not null,
  calculated_at timestamptz not null,
  quality_status text not null,
  quality_reasons jsonb not null default '[]'::jsonb,
  created_at timestamptz not null default now(),
  constraint metric_snapshots_client_fk
    foreign key (client_id) references public.clients (id),
  constraint metric_snapshots_kpi_fk
    foreign key (client_id, kpi_id)
    references public.client_kpis (client_id, id),
  constraint metric_snapshots_client_id_id_unique unique (client_id, id),
  constraint metric_snapshots_metric_key_nonempty check (btrim(metric_key) <> ''),
  constraint metric_snapshots_period_order check (period_end > period_start),
  constraint metric_snapshots_attribution_level_nonempty check (btrim(attribution_level) <> ''),
  constraint metric_snapshots_unit_nonempty check (btrim(unit) <> ''),
  constraint metric_snapshots_currency_format check (
    currency is null or currency ~ '^[A-Z]{3}$'
  ),
  constraint metric_snapshots_formula_version_nonempty check (btrim(formula_version) <> ''),
  constraint metric_snapshots_quality_status_nonempty check (btrim(quality_status) <> ''),
  constraint metric_snapshots_quality_reasons_array check (
    jsonb_typeof(quality_reasons) = 'array'
  )
);

create unique index if not exists metric_snapshots_lineage_unique
  on public.metric_snapshots (
    client_id,
    metric_key,
    period_start,
    period_end,
    attribution_level,
    coalesce(source_entity_id, ''),
    formula_version,
    input_cutoff_at
  );

create index if not exists metric_snapshots_client_period_idx
  on public.metric_snapshots (client_id, period_start, period_end);

create index if not exists metric_snapshots_kpi_period_idx
  on public.metric_snapshots (client_id, kpi_id, period_start desc)
  where kpi_id is not null;

create table if not exists public.reports (
  id uuid primary key default gen_random_uuid(),
  client_id uuid not null,
  period_start timestamptz not null,
  period_end timestamptz not null,
  status text not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint reports_client_fk
    foreign key (client_id) references public.clients (id),
  constraint reports_client_id_id_unique unique (client_id, id),
  constraint reports_period_order check (period_end > period_start),
  constraint reports_status_nonempty check (btrim(status) <> '')
);

create index if not exists reports_client_period_idx
  on public.reports (client_id, period_start desc, period_end desc);

create index if not exists reports_client_status_idx
  on public.reports (client_id, status, updated_at desc);

drop trigger if exists reports_set_updated_at on public.reports;
create trigger reports_set_updated_at
before update on public.reports
for each row execute function public.set_growthbyte_updated_at();

create table if not exists public.report_versions (
  id uuid primary key default gen_random_uuid(),
  client_id uuid not null,
  report_id uuid not null,
  version integer not null,
  schema_version text not null,
  content jsonb not null,
  content_hash text not null,
  status text not null,
  generated_at timestamptz not null default now(),
  generated_by_label text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint report_versions_client_fk
    foreign key (client_id) references public.clients (id),
  constraint report_versions_report_fk
    foreign key (client_id, report_id)
    references public.reports (client_id, id),
  constraint report_versions_client_id_id_unique unique (client_id, id),
  constraint report_versions_report_version_unique
    unique (client_id, report_id, version),
  constraint report_versions_version_positive check (version >= 1),
  constraint report_versions_schema_version_nonempty check (btrim(schema_version) <> ''),
  constraint report_versions_content_hash_nonempty check (btrim(content_hash) <> ''),
  constraint report_versions_status_nonempty check (btrim(status) <> '')
);

create index if not exists report_versions_client_status_idx
  on public.report_versions (client_id, status, generated_at desc);

drop trigger if exists report_versions_set_updated_at on public.report_versions;
create trigger report_versions_set_updated_at
before update on public.report_versions
for each row execute function public.set_growthbyte_updated_at();

-- Normalizes the canonical metric_snapshot_ids array into same-client foreign keys.
create table if not exists public.report_version_metric_snapshots (
  client_id uuid not null,
  report_version_id uuid not null,
  metric_snapshot_id uuid not null,
  created_at timestamptz not null default now(),
  constraint report_version_metric_snapshots_pk
    primary key (client_id, report_version_id, metric_snapshot_id),
  constraint report_version_metric_snapshots_client_fk
    foreign key (client_id) references public.clients (id),
  constraint report_version_metric_snapshots_report_version_fk
    foreign key (client_id, report_version_id)
    references public.report_versions (client_id, id),
  constraint report_version_metric_snapshots_metric_snapshot_fk
    foreign key (client_id, metric_snapshot_id)
    references public.metric_snapshots (client_id, id)
);

create index if not exists report_version_metric_snapshots_metric_idx
  on public.report_version_metric_snapshots (client_id, metric_snapshot_id);

create table if not exists public.audit_events (
  id uuid primary key default gen_random_uuid(),
  client_id uuid not null,
  sync_run_id uuid,
  process_identifier text,
  operator_label text,
  action text not null,
  entity_type text not null,
  entity_id uuid,
  event_metadata jsonb not null default '{}'::jsonb,
  occurred_at timestamptz not null default now(),
  created_at timestamptz not null default now(),
  constraint audit_events_client_fk
    foreign key (client_id) references public.clients (id),
  constraint audit_events_sync_run_fk
    foreign key (client_id, sync_run_id)
    references public.sync_runs (client_id, id),
  constraint audit_events_client_id_id_unique unique (client_id, id),
  constraint audit_events_process_identifier_nonempty check (
    process_identifier is null or btrim(process_identifier) <> ''
  ),
  constraint audit_events_operator_label_nonempty check (
    operator_label is null or btrim(operator_label) <> ''
  ),
  constraint audit_events_action_nonempty check (btrim(action) <> ''),
  constraint audit_events_entity_type_nonempty check (btrim(entity_type) <> ''),
  constraint audit_events_metadata_object check (jsonb_typeof(event_metadata) = 'object')
);

create index if not exists audit_events_client_occurred_idx
  on public.audit_events (client_id, occurred_at desc);

create index if not exists audit_events_entity_idx
  on public.audit_events (client_id, entity_type, entity_id, occurred_at desc);

create index if not exists audit_events_sync_run_idx
  on public.audit_events (client_id, sync_run_id)
  where sync_run_id is not null;

commit;
