/**
 * Journey: GTFS Schedule Data
 * Validates that agency, routes, stops, trips, calendars endpoints return correct data shapes.
 */
import { test, expect } from '@playwright/test';
import { ApiClient } from '../pages/api.client';

test.describe('GTFS Schedule API', () => {
  let client: ApiClient;

  test.beforeEach(({ request }) => {
    client = new ApiClient(request);
  });

  test('GET /api/agency/ returns list with expected fields', async () => {
    const { response, body } = await client.getJson('/api/agency/');

    expect(response.status()).toBe(200);
    expect(Array.isArray(body)).toBe(true);

    if (body.length > 0) {
      const agency = body[0];
      expect(agency).toHaveProperty('agency_id');
      expect(agency).toHaveProperty('agency_name');
      expect(agency).toHaveProperty('agency_url');
      expect(agency).toHaveProperty('agency_timezone');
    }
  });

  test('GET /api/routes/ returns list with expected fields', async () => {
    const { response, body } = await client.getJson('/api/routes/');

    expect(response.status()).toBe(200);
    expect(Array.isArray(body)).toBe(true);

    if (body.length > 0) {
      const route = body[0];
      expect(route).toHaveProperty('route_id');
      expect(route).toHaveProperty('route_type');
    }
  });

  test('GET /api/stops/ returns list with expected fields', async () => {
    const { response, body } = await client.getJson('/api/stops/');

    expect(response.status()).toBe(200);
    expect(Array.isArray(body)).toBe(true);

    if (body.length > 0) {
      const stop = body[0];
      expect(stop).toHaveProperty('stop_id');
      expect(stop).toHaveProperty('stop_name');
    }
  });

  test('GET /api/trips/ returns list with expected fields', async () => {
    const { response, body } = await client.getJson('/api/trips/');

    expect(response.status()).toBe(200);
    expect(Array.isArray(body)).toBe(true);

    if (body.length > 0) {
      const trip = body[0];
      expect(trip).toHaveProperty('trip_id');
      expect(trip).toHaveProperty('route_id');
    }
  });

  test('GET /api/calendars/ returns list with expected fields', async () => {
    const { response, body } = await client.getJson('/api/calendars/');

    expect(response.status()).toBe(200);
    expect(Array.isArray(body)).toBe(true);

    if (body.length > 0) {
      const calendar = body[0];
      expect(calendar).toHaveProperty('service_id');
    }
  });

  test('GET /api/shapes/ returns list', async () => {
    const { response, body } = await client.getJson('/api/shapes/');

    expect(response.status()).toBe(200);
    expect(Array.isArray(body)).toBe(true);
  });

  test('GET /api/stop-times/ returns list with expected fields', async () => {
    const { response, body } = await client.getJson('/api/stop-times/');

    expect(response.status()).toBe(200);
    expect(Array.isArray(body)).toBe(true);

    if (body.length > 0) {
      const stopTime = body[0];
      expect(stopTime).toHaveProperty('trip_id');
      expect(stopTime).toHaveProperty('stop_id');
    }
  });

  test('GET /api/agency/ filter by agency_id works', async () => {
    // First get the list to find a real agency_id
    const { body: agencies } = await client.getJson('/api/agency/');

    if (agencies.length > 0) {
      const agencyId = agencies[0].agency_id;
      const { response, body } = await client.getJson(
        `/api/agency/?agency_id=${encodeURIComponent(agencyId)}`
      );

      expect(response.status()).toBe(200);
      expect(Array.isArray(body)).toBe(true);
      expect(body.length).toBeGreaterThan(0);
      expect(body[0].agency_id).toBe(agencyId);
    } else {
      test.skip(true, 'No agency data available to test filtering');
    }
  });

  test('GET /api/service-today/ returns list for current date', async () => {
    const { response, body } = await client.getJson('/api/service-today/');

    expect(response.status()).toBe(200);
    expect(Array.isArray(body)).toBe(true);
  });
});
