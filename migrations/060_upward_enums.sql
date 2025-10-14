do $$
begin
  if not exists (select 1 from pg_type t join pg_namespace n on n.oid=t.typnamespace
                 where t.typname='hypothesis_status' and n.nspname='public') then
    create type public.hypothesis_status as enum ('proposed','testing','accepted','rejected','archived');
  end if;
  if not exists (select 1 from pg_type t join pg_namespace n on n.oid=t.typnamespace
                 where t.typname='experiment_status' and n.nspname='public') then
    create type public.experiment_status as enum ('planned','running','completed','failed','archived');
  end if;
  if not exists (select 1 from pg_type t join pg_namespace n on n.oid=t.typnamespace
                 where t.typname='aura_status' and n.nspname='public') then
    create type public.aura_status as enum ('proposed','approved','active','paused','completed','rejected');
  end if;
  if not exists (select 1 from pg_type t join pg_namespace n on n.oid=t.typnamespace
                 where t.typname='task_status' and n.nspname='public') then
    create type public.task_status as enum ('todo','doing','blocked','done','dropped');
  end if;
end $$;
