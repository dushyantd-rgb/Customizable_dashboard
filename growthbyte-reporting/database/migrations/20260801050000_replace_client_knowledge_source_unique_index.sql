-- GrowthByte Reporting Platform
-- Phase 2: make client-knowledge source identity usable as an atomic upsert target.

begin;

lock table public.client_knowledge in access exclusive mode;

do $$
declare
  duplicate_identity_count bigint;
begin
  select count(*)
  into duplicate_identity_count
  from (
    select 1
    from public.client_knowledge
    where source_identifier is not null
      and source_version is not null
    group by client_id, source_type, source_identifier, source_version
    having count(*) > 1
  ) as duplicate_identities;

  if duplicate_identity_count > 0 then
    raise exception
      'client_knowledge has % duplicate fully populated source identities',
      duplicate_identity_count
      using errcode = '23505';
  end if;
end;
$$;

-- The constraint drop makes re-entry safe after this migration has already run.
alter table public.client_knowledge
drop constraint if exists client_knowledge_source_version_unique;

drop index if exists public.client_knowledge_source_version_unique;

alter table public.client_knowledge
add constraint client_knowledge_source_version_unique
unique (
  client_id,
  source_type,
  source_identifier,
  source_version
);

commit;
