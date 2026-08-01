-- GrowthByte Reporting Platform
-- Phase 3: encrypted Google OAuth storage and one-Sheet prototype constraints.

begin;

create table if not exists public.google_oauth_credentials (
  id uuid primary key default gen_random_uuid(),
  client_id uuid not null,
  integration_connection_id uuid not null,
  access_ciphertext text not null,
  refresh_ciphertext text,
  expires_at timestamptz not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint google_oauth_credentials_client_fk
    foreign key (client_id) references public.clients (id),
  constraint google_oauth_credentials_connection_fk
    foreign key (client_id, integration_connection_id)
    references public.integration_connections (client_id, id),
  constraint google_oauth_credentials_client_id_id_unique unique (client_id, id),
  constraint google_oauth_credentials_one_per_client unique (client_id),
  constraint google_oauth_credentials_connection_unique
    unique (client_id, integration_connection_id),
  constraint google_oauth_credentials_access_nonempty check (btrim(access_ciphertext) <> ''),
  constraint google_oauth_credentials_refresh_nonempty check (
    refresh_ciphertext is null or btrim(refresh_ciphertext) <> ''
  )
);

create index if not exists google_oauth_credentials_client_expiry_idx
  on public.google_oauth_credentials (client_id, expires_at);

drop trigger if exists google_oauth_credentials_set_updated_at on public.google_oauth_credentials;
create trigger google_oauth_credentials_set_updated_at
before update on public.google_oauth_credentials
for each row execute function public.set_growthbyte_updated_at();

-- The Phase 3 prototype supports exactly one selected worksheet per client.
create unique index if not exists google_sheet_configs_one_per_client_idx
  on public.google_sheet_configs (client_id);

-- Preserve one immutable copy of an unchanged source-row version across repeated sync runs.
create unique index if not exists raw_sheet_rows_source_version_unique_idx
  on public.raw_sheet_rows (
    client_id,
    google_sheet_config_id,
    source_row_key,
    row_hash
  );

commit;
