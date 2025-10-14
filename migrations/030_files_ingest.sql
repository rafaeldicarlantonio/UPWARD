-- Uploaded files
create table if not exists public.files (
  id           uuid primary key default gen_random_uuid(),
  user_id      uuid references public.users(id) on delete set null,
  session_id   uuid references public.sessions(id) on delete set null,
  file_name    text not null,
  mime_type    text,
  bytes        bigint,
  sha256       text,
  storage_key  text, -- pointer to storage path/bucket
  created_at   timestamptz not null default now()
);
create index if not exists ix_files_user on public.files(user_id);

-- Raw chunks (optional; good for audits)
create table if not exists public.chunks (
  id           uuid primary key default gen_random_uuid(),
  file_id      uuid references public.files(id) on delete cascade,
  idx          int not null,
  content      text not null,
  created_at   timestamptz not null default now()
);
create index if not exists ix_chunks_file_idx on public.chunks(file_id, idx);

-- Memories (episodic & semantic distilled units)
-- role_view + provenance added to support UPWARD visibility/provenance needs
create table if not exists public.memories (
  id            uuid primary key default gen_random_uuid(),
  user_id       uuid references public.users(id) on delete set null,
  session_id    uuid references public.sessions(id) on delete set null,
  file_id       uuid references public.files(id) on delete set null,
  type          text not null check (type in ('episodic','semantic','working','procedural')),
  title         text,
  content       text not null,
  summary       text,
  importance    int not null default 0 check (importance between 0 and 10),
  embedding_id  text,  -- pointer in Pinecone or pgvector id
  meta          jsonb not null default '{}'::jsonb,
  role_view     text not null default 'general',             -- visibility tier
  provenance    jsonb not null default '{}'::jsonb,          -- source/citation
  contradictions jsonb not null default '[]'::jsonb,         -- surfaced conflicts
  process_trace_summary text,                                -- compressed REDO view
  created_at    timestamptz not null default now(),
  updated_at    timestamptz not null default now()
);
drop trigger if exists trg_memories_updated on public.memories;
create trigger trg_memories_updated before update on public.memories
for each row execute function set_updated_at();

create index if not exists ix_memories_user_type on public.memories(user_id, type);
create index if not exists ix_memories_session on public.memories(session_id);
create index if not exists ix_memories_file on public.memories(file_id);
