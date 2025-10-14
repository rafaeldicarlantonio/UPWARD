-- Entities (people, orgs, artifacts, concepts)
create table if not exists public.entities (
  id         uuid primary key default gen_random_uuid(),
  name       text not null,
  type       text not null check (type in ('person','org','project','artifact','concept')),
  canonical  boolean not null default false,
  created_at timestamptz not null default now()
);
create unique index if not exists uq_entities_name_type on public.entities(name, type);

-- Mentions (memory ↔ entity)
create table if not exists public.entity_mentions (
  entity_id uuid not null references public.entities(id) on delete cascade,
  memory_id uuid not null references public.memories(id) on delete cascade,
  weight    real not null default 1.0,
  primary key(entity_id, memory_id)
);
create index if not exists ix_entity_mentions_memory on public.entity_mentions(memory_id);

-- Edges (relations across entities; expanded rel_type for UPWARD)
create table if not exists public.entity_edges (
  id        uuid primary key default gen_random_uuid(),
  from_id   uuid not null references public.entities(id) on delete cascade,
  to_id     uuid not null references public.entities(id) on delete cascade,
  rel_type  text not null check (rel_type in (
              'affiliated_with','authored','cites','references','mentions',
              'supports','contradicts','frames','evidence_of','derived_from'
            )),
  weight    real not null default 1.0,
  meta      jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);
create index if not exists ix_entity_edges_from_to on public.entity_edges(from_id, to_id);
