# Website · public landing page

- **Purpose**: this is deliberately tiny. It is a single static Bootstrap landing page mounted at
  the site root (`/`), linking out to the external docs site and the API's ReDoc page. There is no
  domain logic here.
- **Key modules**:
  - `views.py` — one function, `index`, renders `templates/index.html`
  - `urls.py` — one route: `path("", views.index, name="inicio")`
  - `models.py` — empty (no models)
  - `fixtures/auth.json` — seed auth fixture (unrelated to the page itself)

## Data in / data out

- No database reads/writes, no Redis, no queues.
- Serves `GET /` → renders `index.html`, which links to `https://databus.simovilab.org/` (docs)
  and `{% url 'api_docs' %}` (`api`'s ReDoc page).

## Configuration

No app-specific env vars.

## Tests

```
docker compose -f compose.dev.yml run --rm orchestrator uv run pytest website/ -q
```
`website/tests.py` is the empty Django-generated stub — there is nothing to test beyond template
rendering. `make test` runs the full suite.
