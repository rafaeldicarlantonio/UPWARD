-- Users (lightweight; mirror Supabase auth via user_id)
create table if not exists public.users (
  id          uuid primary key default gen_random_uuid(),
  email       text unique,
  display_name text,
  avatar_url  text,
  created_at  timestamptz not null default now()
);

-- API keys (server-to-server or Actions UI)
create table if not exists public.api_keys (
  id          uuid primary key default gen_random_uuid(),
  user_id     uuid references public.users(id) on delete cascade,
  name        text not null,
  token_hash  text not null,
  scopes      text[] not null default '{}',
  created_at  timestamptz not null default now(),
  last_used_at timestamptz
);

-- Sessions (conversation threads)
create table if not exists public.sessions (
  id          uuid primary key default gen_random_uuid(),
  user_id     uuid references public.users(id) on delete set null,
  title       text,
  created_at  timestamptz not null default now(),
  updated_at  timestamptz not null default now()
);
drop trigger if exists trg_sessions_updated on public.sessions;
create trigger trg_sessions_updated before update on public.sessions
for each row execute function set_updated_at();
create index if not exists ix_sessions_user on public.sessions(user_id);
