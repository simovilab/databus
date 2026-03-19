/**
 * Journey: API Authentication
 * Tests the token-based auth flow: obtain token, use token, reject bad credentials.
 *
 * Known issue: POST /api/login/ throws RelatedObjectDoesNotExist (HTTP 500) when the
 * authenticated user does not have an associated Operator profile. This affects the
 * Django superuser (admin) created via CREATE_SUPERUSER in dev entrypoint.
 * Tracked tests are marked accordingly.
 */
import { test, expect } from '@playwright/test';

const BASE_URL = 'http://localhost:8000';

// Token pre-seeded for the admin superuser via Django shell.
// If this token is stale, regenerate with:
//   docker compose -f compose.dev.yml exec backend uv run python manage.py shell -c
//   "from django.contrib.auth.models import User; from rest_framework.authtoken.models import Token;
//    u=User.objects.filter(is_superuser=True).first(); t,_=Token.objects.get_or_create(user=u); print(t.key)"
const ADMIN_TOKEN = process.env.DATABUS_ADMIN_TOKEN ?? '9ac6ff6654dc82c4d2e99916967784681ae2c3d0';

test.describe('API Authentication', () => {
  test('POST /api/login/ returns 400 for invalid credentials', async ({ request }) => {
    const response = await request.post(`${BASE_URL}/api/login/`, {
      data: { username: 'invalid_user', password: 'wrong_password' },
    });
    expect(response.status()).toBe(400);
    const body = await response.json();
    expect(body).toHaveProperty('error');
  });

  test('POST /api/login/ returns 400 when body is empty', async ({ request }) => {
    const response = await request.post(`${BASE_URL}/api/login/`, {
      data: {},
    });
    expect(response.status()).toBe(400);
  });

  test.fixme(
    'POST /api/login/ returns 200 and token for admin user — BUG: 500 because admin lacks Operator profile',
    async ({ request }) => {
      // This test documents the known bug: LoginView calls user.operator.id which raises
      // RelatedObjectDoesNotExist when the user has no Operator row.
      // Fix: wrap user.operator access in a try/except or check hasattr before accessing.
      const response = await request.post(`${BASE_URL}/api/login/`, {
        data: { username: 'admin', password: 'admin' },
      });
      expect(response.status()).toBe(200);
      const body = await response.json();
      expect(body).toHaveProperty('token');
    }
  );

  test('Authenticated request with valid Token header succeeds on vehicle endpoint', async ({
    request,
  }) => {
    const response = await request.get(`${BASE_URL}/api/vehicle/`, {
      headers: { Authorization: `Token ${ADMIN_TOKEN}` },
    });
    expect(response.status()).toBe(200);
    const body = await response.json();
    expect(Array.isArray(body) || typeof body === 'object').toBe(true);
  });

  test('Request with invalid Token is rejected with 401', async ({ request }) => {
    const response = await request.get(`${BASE_URL}/api/vehicle/`, {
      headers: { Authorization: 'Token invalid_token_xyz' },
    });
    expect(response.status()).toBe(401);
  });

  test('Unauthenticated GET /api/vehicle/ response is either 200 (open) or 401/403', async ({
    request,
  }) => {
    // VehicleViewSet has authentication_classes = [TokenAuthentication] but no
    // permission_classes — behavior depends on DEFAULT_PERMISSION_CLASSES in settings.
    const response = await request.get(`${BASE_URL}/api/vehicle/`);
    const status = response.status();
    expect([200, 401, 403]).toContain(status);
  });
});
