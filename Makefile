db-url ?= postgresql://postgres:R6TEmgp1MQMqwY5w@db.juioojpwqstbaqpzujye.supabase.co:5432/postgres
DATABASE_URL ?= $(db-url)

run:
	uvicorn app:app --reload --port 8000

test:
	pytest -q

selftest:
	curl -s http://localhost:8000/docs >/dev/null && echo OK || echo FAIL

migrate:
	psql "$(DATABASE_URL)" -f migrations/20251013_upward_core.sql
