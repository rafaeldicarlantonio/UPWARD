-- UUIDs + basics
create extension if not exists "pgcrypto";
create extension if not exists "uuid-ossp";

-- Updated-at helper
create or replace function set_updated_at() returns trigger language plpgsql as $$
begin
  new.updated_at = now();
  return new;
end $$;
