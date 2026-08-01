-- GrowthByte Reporting Platform
-- Phase 3: Meta Ads integration tables for accounts, campaigns, ad sets, ads, and insights.

begin;

create table if not exists public.meta_accounts (
  id uuid primary key default gen_random_uuid(),
  client_id uuid not null,
  integration_connection_id uuid not null,
  external_account_id text not null,
  name text,
  currency char(3),
  account_timezone text,
  status text not null,
  last_seen_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint meta_accounts_client_fk
    foreign key (client_id) references public.clients (id),
  constraint meta_accounts_connection_fk
    foreign key (client_id, integration_connection_id)
    references public.integration_connections (client_id, id),
  constraint meta_accounts_client_id_id_unique unique (client_id, id),
  constraint meta_accounts_one_per_client unique (client_id),
  constraint meta_accounts_connection_unique
    unique (client_id, integration_connection_id),
  constraint meta_accounts_source_unique
    unique (client_id, external_account_id),
  constraint meta_accounts_external_account_id_nonempty check (btrim(external_account_id) <> ''),
  constraint meta_accounts_status_nonempty check (btrim(status) <> '')
);

create index if not exists meta_accounts_client_status_idx
  on public.meta_accounts (client_id, status);

drop trigger if exists meta_accounts_set_updated_at on public.meta_accounts;
create trigger meta_accounts_set_updated_at
before update on public.meta_accounts
for each row execute function public.set_growthbyte_updated_at();

create table if not exists public.meta_campaigns (
  id uuid primary key default gen_random_uuid(),
  client_id uuid not null,
  meta_account_id uuid not null,
  external_campaign_id text not null,
  name text,
  objective text,
  status text,
  effective_status text,
  source_created_at timestamptz,
  source_updated_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint meta_campaigns_client_fk
    foreign key (client_id) references public.clients (id),
  constraint meta_campaigns_meta_account_fk
    foreign key (client_id, meta_account_id)
    references public.meta_accounts (client_id, id),
  constraint meta_campaigns_client_id_id_unique unique (client_id, id),
  constraint meta_campaigns_source_unique
    unique (client_id, meta_account_id, external_campaign_id),
  constraint meta_campaigns_external_campaign_id_nonempty check (btrim(external_campaign_id) <> '')
);

create index if not exists meta_campaigns_client_account_idx
  on public.meta_campaigns (client_id, meta_account_id);

create index if not exists meta_campaigns_client_status_idx
  on public.meta_campaigns (client_id, status);

drop trigger if exists meta_campaigns_set_updated_at on public.meta_campaigns;
create trigger meta_campaigns_set_updated_at
before update on public.meta_campaigns
for each row execute function public.set_growthbyte_updated_at();

create table if not exists public.meta_ad_sets (
  id uuid primary key default gen_random_uuid(),
  client_id uuid not null,
  meta_account_id uuid not null,
  campaign_id uuid not null,
  external_ad_set_id text not null,
  name text,
  objective text,
  status text,
  effective_status text,
  source_created_at timestamptz,
  source_updated_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint meta_ad_sets_client_fk
    foreign key (client_id) references public.clients (id),
  constraint meta_ad_sets_meta_account_fk
    foreign key (client_id, meta_account_id)
    references public.meta_accounts (client_id, id),
  constraint meta_ad_sets_campaign_fk
    foreign key (client_id, campaign_id)
    references public.meta_campaigns (client_id, id),
  constraint meta_ad_sets_client_id_id_unique unique (client_id, id),
  constraint meta_ad_sets_source_unique
    unique (client_id, meta_account_id, external_ad_set_id),
  constraint meta_ad_sets_external_ad_set_id_nonempty check (btrim(external_ad_set_id) <> '')
);

create index if not exists meta_ad_sets_client_campaign_idx
  on public.meta_ad_sets (client_id, campaign_id);

drop trigger if exists meta_ad_sets_set_updated_at on public.meta_ad_sets;
create trigger meta_ad_sets_set_updated_at
before update on public.meta_ad_sets
for each row execute function public.set_growthbyte_updated_at();

create table if not exists public.meta_ads (
  id uuid primary key default gen_random_uuid(),
  client_id uuid not null,
  meta_account_id uuid not null,
  campaign_id uuid not null,
  ad_set_id uuid not null,
  external_ad_id text not null,
  name text,
  creative_id text,
  status text,
  effective_status text,
  source_created_at timestamptz,
  source_updated_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint meta_ads_client_fk
    foreign key (client_id) references public.clients (id),
  constraint meta_ads_meta_account_fk
    foreign key (client_id, meta_account_id)
    references public.meta_accounts (client_id, id),
  constraint meta_ads_campaign_fk
    foreign key (client_id, campaign_id)
    references public.meta_campaigns (client_id, id),
  constraint meta_ads_ad_set_fk
    foreign key (client_id, ad_set_id)
    references public.meta_ad_sets (client_id, id),
  constraint meta_ads_client_id_id_unique unique (client_id, id),
  constraint meta_ads_source_unique
    unique (client_id, meta_account_id, external_ad_id),
  constraint meta_ads_external_ad_id_nonempty check (btrim(external_ad_id) <> '')
);

create index if not exists meta_ads_client_ad_set_idx
  on public.meta_ads (client_id, ad_set_id);

drop trigger if exists meta_ads_set_updated_at on public.meta_ads;
create trigger meta_ads_set_updated_at
before update on public.meta_ads
for each row execute function public.set_growthbyte_updated_at();

create table if not exists public.meta_daily_insights (
  id uuid primary key default gen_random_uuid(),
  client_id uuid not null,
  meta_account_id uuid not null,
  report_date date not null,
  entity_level text not null,
  entity_id uuid,
  external_entity_id text not null,
  spend numeric(20,6) not null,
  currency char(3) not null,
  impressions bigint not null default 0,
  reach bigint not null default 0,
  clicks bigint not null default 0,
  meta_leads bigint not null default 0,
  meta_conversions bigint not null default 0,
  conversion_value numeric(20,6),
  raw_metrics jsonb not null default '{}'::jsonb,
  sync_run_id uuid,
  source_updated_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint meta_daily_insights_client_fk
    foreign key (client_id) references public.clients (id),
  constraint meta_daily_insights_meta_account_fk
    foreign key (client_id, meta_account_id)
    references public.meta_accounts (client_id, id),
  constraint meta_daily_insights_sync_run_fk
    foreign key (client_id, sync_run_id)
    references public.sync_runs (client_id, id),
  constraint meta_daily_insights_client_id_id_unique unique (client_id, id),
  constraint meta_daily_insights_entity_level_check check (
    entity_level in ('campaign', 'ad_set', 'ad')
  ),
  constraint meta_daily_insights_external_entity_id_nonempty check (btrim(external_entity_id) <> '')
);

create unique index if not exists meta_daily_insights_source_unique
  on public.meta_daily_insights (client_id, meta_account_id, report_date, entity_level, external_entity_id);

create index if not exists meta_daily_insights_client_date_idx
  on public.meta_daily_insights (client_id, report_date desc);

create index if not exists meta_daily_insights_client_account_date_idx
  on public.meta_daily_insights (client_id, meta_account_id, report_date desc);

drop trigger if exists meta_daily_insights_set_updated_at on public.meta_daily_insights;
create trigger meta_daily_insights_set_updated_at
before update on public.meta_daily_insights
for each row execute function public.set_growthbyte_updated_at();

commit;
