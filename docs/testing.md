# Testing

## Quick checks after a merge

```bash
# venv activated, repo root
python scripts/smoke_test.py
```

`scripts/smoke_test.py` delegates to pytest (see below).

## Unit / API tests (pytest)

Install test extras (pytest is listed in `requirements-api.txt`):

```bash
pip install -r requirements-api.txt
pytest
```

Useful variants:

```bash
pytest -q
pytest tests/test_inventory_api.py -q
pytest -k sell
```

### What is covered

| Area | Location |
|------|----------|
| Config helpers | `tests/test_config.py` |
| Pydantic schemas | `tests/test_schemas.py` |
| Auth / roles / audit | `tests/test_auth.py` |
| Health, errors, pagination, S3/local OCR, full API contract | `tests/test_api_polish.py` |
| Inventory + transactional sell + vector sync failures | `tests/test_inventory_api.py` |
| OCR temp-file cleanup | `tests/test_ocr_api.py` |
| SQLite vector stub (no embedder) | `tests/test_vector_search_lazy.py` |
| pgvector unit (mocked Postgres path) | `tests/test_pgvector_unit.py` |
| Optional Docker pgvector IT | `tests/test_pgvector_docker.py` (`RUN_PGVECTOR_IT=1`) |

OCR/Gemini are stubbed in `tests/conftest.py`. Default suite uses SQLite (vectors stubbed). For live Postgres:

```bash
docker compose -f docker-compose.pgvector.yml up -d
set RUN_PGVECTOR_IT=1
pytest tests/test_pgvector_docker.py
# or: python scripts/docker_pgvector_smoke.py
```


### Conventions

- Prefer pytest fixtures in `conftest.py` over one-off smoke scripts for new coverage.
- Keep invoice JSON field names (`items`, `unit_price`, `subtotal`, `total`, `timestamp`) asserted when touching sell.
- Use a temp `DATABASE_URL` — never point tests at production `pharma.db`.
