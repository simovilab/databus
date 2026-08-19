.PHONY: lint typecheck test

# ruff needs no Django settings (no settings import), so it runs locally
# against the backend project without going through Docker.
lint:
	cd backend && uv run ruff check .

# mypy loads the django-stubs plugin, which imports databus.settings; that
# module reads env vars via python-decouple and fails to import outside the
# dev container, so mypy must run inside it.
typecheck:
	docker compose -f compose.dev.yml run --rm orchestrator uv run mypy .

# pytest-django also needs the real settings/DB, so it runs inside the dev
# container too.
test:
	docker compose -f compose.dev.yml run --rm orchestrator uv run pytest -q
