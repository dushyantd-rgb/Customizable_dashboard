-- GrowthByte Reporting Platform
-- Phase 2: non-secret integration metadata and versioned Sheet mappings.

begin;

create table if not exists public.integration_connections (
  id uuid primary key default gen_random_uuid(),
  client_id uuid not null,
  provider text not null,
  source_identifier text,
  display_name text,
  status text not null,
  last_connected_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint integration_connections_client_fk
    foreign key (client_id) references public.clients (id),
  constraint integration_connections_client_id_id_unique unique (client_id, id),
  constraint integration_connections_provider_nonempty check (btrim(provider) <> ''),
  constraint integration_connections_status_nonempty check (btrim(status) <> '')
);

create unique index if not exists integration_connections_source_unique
  on public.integration_connections (client_id, provider, source_identifier)
  where source_identifier is not null;

create index if not exists integration_connections_client_status_idx
  on public.integration_connections (client_id, provider, status);

drop trigger if exists integration_connections_set_updated_at on public.integration_connections;
create trigger integration_connections_set_updated_at
before update on public.integration_connections
for each row execute function public.set_growthbyte_updated_at();

create table if not exists public.google_sheet_configs (
  id uuid primary key default gen_random_uuid(),
  client_id uuid not null,
  integration_connection_id uuid,
  spreadsheet_id text not null,
  worksheet_name text not null,
  header_row integer not null,
  data_start_row integer not null,
  source_timezone text not null,
  status text not null,
  mapping_version integer not null default 1,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint google_sheet_configs_client_fk
    foreign key (client_id) references public.clients (id),
  constraint google_sheet_configs_connection_fk
    foreign key (client_id, integration_connection_id)
    references public.integration_connections (client_id, id),
  constraint google_sheet_configs_client_id_id_unique unique (client_id, id),
  constraint google_sheet_configs_source_unique
    unique (client_id, spreadsheet_id, worksheet_name),
  constraint google_sheet_configs_spreadsheet_id_nonempty check (btrim(spreadsheet_id) <> ''),
  constraint google_sheet_configs_worksheet_name_nonempty check (btrim(worksheet_name) <> ''),
  constraint google_sheet_configs_header_row_positive check (header_row >= 1),
  constraint google_sheet_configs_data_start_after_header check (data_start_row > header_row),
  constraint google_sheet_configs_source_timezone_nonempty check (btrim(source_timezone) <> ''),
  constraint google_sheet_configs_status_nonempty check (btrim(status) <> ''),
  constraint google_sheet_configs_mapping_version_positive check (mapping_version >= 1)
);

create index if not exists google_sheet_configs_client_status_idx
  on public.google_sheet_configs (client_id, status);

create index if not exists google_sheet_configs_connection_idx
  on public.google_sheet_configs (client_id, integration_connection_id)
  where integration_connection_id is not null;

drop trigger if exists google_sheet_configs_set_updated_at on public.google_sheet_configs;
create trigger google_sheet_configs_set_updated_at
before update on public.google_sheet_configs
for each row execute function public.set_growthbyte_updated_at();

create table if not exists public.field_mappings (
  id uuid primary key default gen_random_uuid(),
  client_id uuid not null,
  google_sheet_config_id uuid not null,
  source_header text not null,
  canonical_field text not null,
  transform jsonb not null default '{}'::jsonb,
  required boolean not null default false,
  version integer not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint field_mappings_client_fk
    foreign key (client_id) references public.clients (id),
  constraint field_mappings_config_fk
    foreign key (client_id, google_sheet_config_id)
    references public.google_sheet_configs (client_id, id),
  constraint field_mappings_client_id_id_unique unique (client_id, id),
  constraint field_mappings_source_version_unique
    unique (client_id, google_sheet_config_id, source_header, version),
  constraint field_mappings_source_header_nonempty check (btrim(source_header) <> ''),
  constraint field_mappings_canonical_field_nonempty check (btrim(canonical_field) <> ''),
  constraint field_mappings_version_positive check (version >= 1)
);

create index if not exists field_mappings_config_version_idx
  on public.field_mappings (client_id, google_sheet_config_id, version);

drop trigger if exists field_mappings_set_updated_at on public.field_mappings;
create trigger field_mappings_set_updated_at
before update on public.field_mappings
for each row execute function public.set_growthbyte_updated_at();

create table if not exists public.status_mappings (
  id uuid primary key default gen_random_uuid(),
  client_id uuid not null,
  google_sheet_config_id uuid not null,
  source_value_normalized text not null,
  canonical_status text not null,
  counts_as_reviewed boolean not null,
  mapping_version integer not null,
  approved_by_label text,
  approved_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint status_mappings_client_fk
    foreign key (client_id) references public.clients (id),
  constraint status_mappings_config_fk
    foreign key (client_id, google_sheet_config_id)
    references public.google_sheet_configs (client_id, id),
  constraint status_mappings_client_id_id_unique unique (client_id, id),
  constraint status_mappings_source_version_unique
    unique (client_id, google_sheet_config_id, source_value_normalized, mapping_version),
  constraint status_mappings_source_value_nonempty check (btrim(source_value_normalized) <> ''),
  constraint status_mappings_canonical_status_nonempty check (btrim(canonical_status) <> ''),
  constraint status_mappings_mapping_version_positive check (mapping_version >= 1),
  constraint status_mappings_approval_pair check (
    (approved_by_label is null and approved_at is null)
    or (approved_by_label is not null and btrim(approved_by_label) <> '' and approved_at is not null)
  )
);

create index if not exists status_mappings_config_version_idx
  on public.status_mappings (client_id, google_sheet_config_id, mapping_version);

drop trigger if exists status_mappings_set_updated_at on public.status_mappings;
create trigger status_mappings_set_updated_at
before update on public.status_mappings
for each row execute function public.set_growthbyte_updated_at();

commit;
