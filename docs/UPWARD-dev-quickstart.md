## UPWARD Dev Quickstart

- Set `DATABASE_URL` to your Postgres connection string.
- Run migrations:

```bash
make migrate
```

If `psql` is not available in CI:

### Option A: Supabase CLI
- Install: see `https://supabase.com/docs/guides/cli`.
- Run SQL using your env URL:
```bash
supabase db query --db-url "$DATABASE_URL" < migrations/20251013_upward_core.sql
```

### Option B: Docker Postgres client
```bash
docker run --rm -e DATABASE_URL -v "$PWD:/work" -w /work postgres:16 \
  psql "$DATABASE_URL" -f migrations/20251013_upward_core.sql
```

Notes:
- `make migrate` uses `psql "$(DATABASE_URL)"` and falls back to a default `db-url` if `DATABASE_URL` is not set.
- Ensure network/firewall allows connections from your runner to the database.
