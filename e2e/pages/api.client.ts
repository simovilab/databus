import { type APIRequestContext, expect } from '@playwright/test';

const BASE_URL = 'http://localhost:8000';

// Pre-seeded admin token (superuser created in dev via docker-entrypoint.sh).
// Override via DATABUS_ADMIN_TOKEN environment variable.
// To regenerate:
//   docker compose -f compose.dev.yml exec backend uv run python manage.py shell -c \
//   "from django.contrib.auth.models import User; from rest_framework.authtoken.models import Token; \
//    u=User.objects.filter(is_superuser=True).first(); t,_=Token.objects.get_or_create(user=u); print(t.key)"
export const ADMIN_TOKEN =
  process.env.DATABUS_ADMIN_TOKEN ?? '9ac6ff6654dc82c4d2e99916967784681ae2c3d0';

export class ApiClient {
  readonly request: APIRequestContext;

  constructor(request: APIRequestContext) {
    this.request = request;
  }

  authHeaders(): Record<string, string> {
    return { Authorization: `Token ${ADMIN_TOKEN}` };
  }

  async get(path: string, authenticated = false) {
    const headers = authenticated ? this.authHeaders() : {};
    return this.request.get(`${BASE_URL}${path}`, { headers });
  }

  async getJson(path: string, authenticated = false) {
    const response = await this.get(path, authenticated);
    return { response, body: await response.json() };
  }
}
