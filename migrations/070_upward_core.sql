-- Hypotheses
create table if not exists public.hypotheses (
  id               uuid primary key default gen_random_uuid(),
  created_at       timestamptz not null default now(),
  created_by       uuid references public.users(id) on delete set null,
  title            text not null,
  description      text,
  status           public.hypothesis_status not null default 'proposed',
  source_message_id uuid references public.messages(id) on delete set null,
  pareto_score     real,
  external_compare boolean not null default false,
  compare_summary  jsonb not null default '{}'::jsonb,
  contradictions   jsonb not null default '[]'::jsonb,
  provenance       jsonb not null default '{}'::jsonb
);
create index if not exists ix_hypotheses_status on public.hypotheses(status);
create index if not exists ix_hypotheses_creator on public.hypotheses(created_by);

-- Experiments
create table if not exists public.experiments (
  id               uuid primary key default gen_random_uuid(),
  hypothesis_id    uuid not null references public.hypotheses(id) on delete cascade,
  created_at       timestamptz not null default now(),
  created_by       uuid references public.users(id) on delete set null,
  method           text,
  metrics          jsonb not null default '{}'::jsonb,
  status           public.experiment_status not null default 'planned',
  result_summary   text,
  artifacts        jsonb not null default '{}'::jsonb
);
create index if not exists ix_experiments_hypothesis on public.experiments(hypothesis_id);

-- AURA projects/tasks
create table if not exists public.aura_projects (
  id                 uuid primary key default gen_random_uuid(),
  created_at         timestamptz not null default now(),
  created_by         uuid references public.users(id) on delete set null,
  title              text not null,
  description        text,
  status             public.aura_status not null default 'proposed',
  linked_hypothesis_id uuid references public.hypotheses(id) on delete set null,
  tags               text[] not null default '{}'
);
create index if not exists ix_aura_projects_status on public.aura_projects(status);

create table if not exists public.aura_tasks (
  id           uuid primary key default gen_random_uuid(),
  project_id   uuid not null references public.aura_projects(id) on delete cascade,
  created_at   timestamptz not null default now(),
  created_by   uuid references public.users(id) on delete set null,
  title        text not null,
  description  text,
  status       public.task_status not null default 'todo',
  assignee     uuid references public.users(id) on delete set null,
  due_date     date,
  meta         jsonb not null default '{}'::jsonb
);
create index if not exists ix_aura_tasks_project on public.aura_tasks(project_id, status);

-- REDO / Rheomode process ledger
create table if not exists public.rheomode_runs (
  id                     uuid primary key default gen_random_uuid(),
  created_at             timestamptz not null default now(),
  session_id             uuid not null references public.sessions(id) on delete cascade,
  message_id             uuid references public.messages(id) on delete cascade,
  role                   text not null,
  process_trace          jsonb not null default '{}'::jsonb,
  process_trace_summary  text,
  lift_score             real,
  contradiction_score    real
);
create index if not exists ix_rheomode_runs_session on public.rheomode_runs(session_id, created_at);

-- External compare whitelist
create table if not exists public.external_sources_whitelist (
  source_id   text primary key,
  label       text,
  priority    int not null default 0,
  url_pattern text not null,
  enabled     boolean not null default true,
  meta        jsonb not null default '{}'::jsonb
);
create index if not exists ix_whitelist_enabled on public.external_sources_whitelist(enabled, priority desc);
