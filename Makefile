run:
	uvicorn app:app --reload --port 8000

test:
	pytest -q

selftest:
	curl -s http://localhost:8000/docs >/dev/null && echo OK || echo FAIL
