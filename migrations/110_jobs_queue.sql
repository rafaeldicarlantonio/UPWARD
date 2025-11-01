-- Jobs queue for background tasks
create table if not exists public.jobs (
  id           uuid primary key default gen_random_uuid(),
  job_type     text not null,
  payload      jsonb not null default '{}'::jsonb,
  status       text not null check (status in ('pending','processing','completed','failed')),
  created_at   timestamptz not null default now(),
  started_at   timestamptz,
  completed_at timestamptz,
  error        text,
  retry_count  int not null default 0,
  max_retries  int not null default 3
);

-- Indexes for efficient job processing
create index if not exists ix_jobs_status_type on public.jobs(status, job_type);
create index if not exists ix_jobs_created_at on public.jobs(created_at);
create index if not exists ix_jobs_status_created on public.jobs(status, created_at) where status = 'pending';
