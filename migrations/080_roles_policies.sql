-- Roles and assignments
create table if not exists public.roles (
  role_key  text primary key,  -- 'general','pro','scholars','analytics','ops'
  label     text not null
);

create table if not exists public.user_roles (
  user_id   uuid references public.users(id) on delete cascade,
  role_key  text references public.roles(role_key) on delete cascade,
  primary key(user_id, role_key)
);

-- If you intend to enable RLS, keep policies simple at first.
-- You can run these AFTER you confirm app code passes the right JWT claims.

-- Sample RLS enable (comment out if not using RLS yet)
-- alter table public.hypotheses enable row level security;
-- create policy hyp_read on public.hypotheses for select using (true);
-- create policy hyp_write on public.hypotheses for insert with check (
--   exists (select 1 from public.user_roles ur where ur.user_id = auth.uid() and ur.role_key in ('pro','scholars','analytics'))
-- );
-- create policy hyp_update on public.hypotheses for update using (
--   exists (select 1 from public.user_roles ur where ur.user_id = auth.uid() and ur.role_key in ('pro','scholars','analytics'))
-- );
