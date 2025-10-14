-- Evaluations (offline tests, golden sets, replay traces)
create table if not exists public.evals (
  id          uuid primary key default gen_random_uuid(),
  name        text not null,
  suite       text not null,
  inputs      jsonb not null default '{}'::jsonb,
  expected    jsonb not null default '{}'::jsonb,
  got         jsonb not null default '{}'::jsonb,
  passed      boolean,
  created_at  timestamptz not null default now()
);

-- Feature flags
create table if not exists public.feature_flags (
  key         text primary key,
  value       jsonb not null default '{}'::jsonb,
  updated_at  timestamptz not null default now()
);
