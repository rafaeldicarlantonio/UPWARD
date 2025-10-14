-- Messages in a session
create table if not exists public.messages (
  id           uuid primary key default gen_random_uuid(),
  session_id   uuid not null references public.sessions(id) on delete cascade,
  role         text not null check (role in ('user','assistant','system','tool')),
  content      text not null,
  meta         jsonb not null default '{}'::jsonb,
  created_at   timestamptz not null default now()
);
create index if not exists ix_messages_session_created on public.messages(session_id, created_at);

-- Tool runs / reviewer passes / eval traces
create table if not exists public.tool_runs (
  id           uuid primary key default gen_random_uuid(),
  message_id   uuid references public.messages(id) on delete cascade,
  name         text not null,
  status       text not null check (status in ('ok','error','skipped')),
  payload      jsonb not null default '{}'::jsonb,
  created_at   timestamptz not null default now()
);
create index if not exists ix_tool_runs_message on public.tool_runs(message_id);

