# E2E Tests — databus

Playwright end-to-end tests for the databus transit data platform.

## Prerequisites

- Node.js 18+
- Services running via `docker compose -f compose.dev.yml up`
- Backend reachable at http://localhost:8000

## Setup

```bash
cd e2e
npm install
npx playwright install chromium
```

## Running Tests

```bash
# All tests (headless)
npm test

# With visible browser
npm run test:headed

# Step-through debugger
npm run test:debug

# Open HTML report from last run
npm run test:report
```

## Test Suites

| File | Journey |
|---|---|
| `01-api-health.spec.ts` | API root, OpenAPI schema, ReDoc docs |
| `02-api-authentication.spec.ts` | Token auth — happy path, bad credentials, invalid token |
| `03-gtfs-schedule.spec.ts` | GTFS Schedule data — agencies, routes, stops, trips, calendars, shapes |
| `04-feed-realtime.spec.ts` | Real-time feed data — companies, vehicles, runs, operators, positions |
| `05-django-admin.spec.ts` | Django Admin — login, list views, logout |

## Authentication

Tests authenticate using a pre-seeded admin token. Override via environment variable:

```bash
DATABUS_ADMIN_TOKEN=<your-token> npm test
```

To regenerate the token after a database reset:

```bash
docker compose -f compose.dev.yml exec backend uv run python manage.py shell -c \
  "from django.contrib.auth.models import User; from rest_framework.authtoken.models import Token; \
   u=User.objects.filter(is_superuser=True).first(); t,_=Token.objects.get_or_create(user=u); print(t.key)"
```

Then update the fallback value in `pages/api.client.ts` and `tests/02-api-authentication.spec.ts`.

## Artifacts

Generated under `artifacts/` (git-ignored):

| Path | Contents |
|---|---|
| `artifacts/html-report/` | HTML report — open with `npm run test:report` |
| `artifacts/results.xml` | JUnit XML for CI |
| `artifacts/test-results/` | Screenshots, videos, and traces (failures only) |

## Known Issues

**`POST /api/login/` returns HTTP 500 for the admin superuser** — `LoginView` unconditionally accesses `user.operator.id`, but the superuser has no `Operator` row. The test in `02-api-authentication.spec.ts` is marked `test.fixme()` until this is resolved.

Fix: in `backend/api/views.py`, guard the operator access:
```python
operator = getattr(user, 'operator', None)
operator_id = operator.id if operator else None
```

## Project Structure

```
e2e/
├── pages/
│   ├── api.client.ts       # API request helper (token auth)
│   └── admin.page.ts       # Page Object for Django Admin
├── tests/
│   ├── 01-api-health.spec.ts
│   ├── 02-api-authentication.spec.ts
│   ├── 03-gtfs-schedule.spec.ts
│   ├── 04-feed-realtime.spec.ts
│   └── 05-django-admin.spec.ts
├── artifacts/              # Generated — git-ignored
├── playwright.config.ts
├── package.json
└── tsconfig.json
```
