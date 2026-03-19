/**
 * Journey: API Health & Root
 * Validates that the API root and schema endpoints are accessible and return expected structure.
 */
import { test, expect } from '@playwright/test';
import { ApiClient } from '../pages/api.client';

test.describe('API Health', () => {
  test('API root returns all registered endpoints', async ({ request }) => {
    const client = new ApiClient(request);
    const { response, body } = await client.getJson('/api/');

    expect(response.status()).toBe(200);

    // Core feed endpoints
    expect(body).toHaveProperty('company');
    expect(body).toHaveProperty('vehicle');
    expect(body).toHaveProperty('run');

    // GTFS schedule endpoints
    expect(body).toHaveProperty('agency');
    expect(body).toHaveProperty('stops');
    expect(body).toHaveProperty('routes');
    expect(body).toHaveProperty('trips');
    expect(body).toHaveProperty('calendars');

    // Verify URLs point to the correct host
    expect(body.agency).toContain('/api/agency/');
    expect(body.routes).toContain('/api/routes/');
  });

  test('API docs (ReDoc) endpoint is accessible', async ({ page }) => {
    const response = await page.goto('/api/docs/');
    expect(response?.status()).toBe(200);

    // ReDoc renders an HTML page — check that the page title or ReDoc element is present
    await expect(page).toHaveTitle(/api|databus|redoc/i);
  });

  test('API schema file (YAML) is downloadable', async ({ request }) => {
    const client = new ApiClient(request);
    const response = await client.get('/api/docs/schema/');

    // Schema endpoint serves the realtime.yml file
    expect(response.status()).toBe(200);
    const contentType = response.headers()['content-type'];
    expect(contentType).toMatch(/yaml|octet-stream|force-download/i);
  });
});
