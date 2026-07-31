-- GrowthByte Reporting Platform
-- Phase 2: client, knowledge, and KPI foundations.

begin;

create extension if not exists pgcrypto;

create or replace function public.set_growthbyte_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

create table if not exists public.clients (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  slug text not null,
  reporting_timezone text not null,
  default_currency character(3) not null,
  status text not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint clients_name_nonempty check (btrim(name) <> ''),
  constraint clients_name_length check (char_length(name) <= 200),
  constraint clients_slug_format check (slug ~ '^[a-z0-9]+(?:-[a-z0-9]+)*$'),
  constraint clients_reporting_timezone_nonempty check (btrim(reporting_timezone) <> ''),
  constraint clients_default_currency_format check (default_currency ~ '^[A-Z]{3}$'),
  constraint clients_status_nonempty check (btrim(status) <> ''),
  constraint clients_slug_unique unique (slug)
);

drop trigger if exists clients_set_updated_at on public.clients;
create trigger clients_set_updated_at
before update on public.clients
for each row execute function public.set_growthbyte_updated_at();

create table if not exists public.client_knowledge (
  id uuid primary key default gen_random_uuid(),
  client_id uuid not null,
  category text not null,
  knowledge_key text not null,
  value jsonb not null,
  status text not null,
  source_type text not null,
  source_identifier text,
  source_display_name text,
  source_reference text,
  source_version text,
  source_hash text,
  import_batch_id uuid,
  imported_at timestamptz,
  version integer not null default 1,
  approved_by_label text,
  approved_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint client_knowledge_client_fk
    foreign key (client_id) references public.clients (id),
  constraint client_knowledge_client_id_id_unique unique (client_id, id),
  constraint client_knowledge_semantic_version_unique
    unique (client_id, category, knowledge_key, version),
  constraint client_knowledge_category_nonempty check (btrim(category) <> ''),
  constraint client_knowledge_key_nonempty check (btrim(knowledge_key) <> ''),
  constraint client_knowledge_status_nonempty check (btrim(status) <> ''),
  constraint client_knowledge_source_type_nonempty check (btrim(source_type) <> ''),
  constraint client_knowledge_version_positive check (version >= 1),
  constraint client_knowledge_approval_pair check (
    (approved_by_label is null and approved_at is null)
    or (approved_by_label is not null and btrim(approved_by_label) <> '' and approved_at is not null)
  )
);

create unique index if not exists client_knowledge_source_version_unique
  on public.client_knowledge (client_id, source_type, source_identifier, source_version)
  where source_identifier is not null and source_version is not null;

create index if not exists client_knowledge_client_status_idx
  on public.client_knowledge (client_id, status);

create index if not exists client_knowledge_client_imported_idx
  on public.client_knowledge (client_id, imported_at desc)
  where imported_at is not null;

drop trigger if exists client_knowledge_set_updated_at on public.client_knowledge;
create trigger client_knowledge_set_updated_at
before update on public.client_knowledge
for each row execute function public.set_growthbyte_updated_at();

create table if not exists public.client_kpis (
  id uuid primary key default gen_random_uuid(),
  client_id uuid not null,
  metric_key text not null,
  label text not null,
  target_value numeric,
  unit text not null,
  direction text not null,
  attribution_level text not null,
  active_from date not null,
  active_to date,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint client_kpis_client_fk
    foreign key (client_id) references public.clients (id),
  constraint client_kpis_client_id_id_unique unique (client_id, id),
  constraint client_kpis_effective_version_unique
    unique (client_id, metric_key, active_from),
  constraint client_kpis_metric_key_nonempty check (btrim(metric_key) <> ''),
  constraint client_kpis_label_nonempty check (btrim(label) <> ''),
  constraint client_kpis_label_length check (char_length(label) <= 120),
  constraint client_kpis_unit_nonempty check (btrim(unit) <> ''),
  constraint client_kpis_direction_nonempty check (btrim(direction) <> ''),
  constraint client_kpis_attribution_level_nonempty check (btrim(attribution_level) <> ''),
  constraint client_kpis_active_interval check (active_to is null or active_to >= active_from)
);

create index if not exists client_kpis_client_active_idx
  on public.client_kpis (client_id, active_from, active_to);

drop trigger if exists client_kpis_set_updated_at on public.client_kpis;
create trigger client_kpis_set_updated_at
before update on public.client_kpis
for each row execute function public.set_growthbyte_updated_at();

commit;
