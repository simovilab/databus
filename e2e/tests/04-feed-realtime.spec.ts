/**
 * Journey: Feed / Real-time Data
 * Validates company, vehicle, run, position endpoints for the feed/realtime app.
 * Uses pre-seeded admin token for TokenAuthentication-protected endpoints.
 */
import { test, expect } from '@playwright/test';
import { ApiClient } from '../pages/api.client';

test.describe('Feed / Real-time API', () => {
  test('GET /api/company/ returns list (public — authentication_classes not set)', async ({
    request,
  }) => {
    const client = new ApiClient(request);
    // CompanyViewSet has authentication_classes commented out — accessible without token
    const { response, body } = await client.getJson('/api/company/');

    expect(response.status()).toBe(200);
    expect(Array.isArray(body)).toBe(true);
  });

  test('GET /api/vehicle/ returns list when authenticated', async ({ request }) => {
    const client = new ApiClient(request);
    const { response, body } = await client.getJson('/api/vehicle/', true);

    expect(response.status()).toBe(200);
    expect(Array.isArray(body)).toBe(true);
  });

  test('GET /api/run/ returns list when authenticated', async ({ request }) => {
    const client = new ApiClient(request);
    const { response, body } = await client.getJson('/api/run/', true);

    expect(response.status()).toBe(200);
    expect(Array.isArray(body)).toBe(true);
  });

  test('GET /api/operator/ returns list when authenticated', async ({ request }) => {
    const client = new ApiClient(request);
    const { response, body } = await client.getJson('/api/operator/', true);

    expect(response.status()).toBe(200);
    expect(Array.isArray(body)).toBe(true);
  });

  test('GET /api/position/ returns list when authenticated', async ({ request }) => {
    const client = new ApiClient(request);
    const { response, body } = await client.getJson('/api/position/', true);

    expect(response.status()).toBe(200);
    expect(Array.isArray(body)).toBe(true);
  });

  test('GET /api/data-provider/ returns list when authenticated', async ({ request }) => {
    const client = new ApiClient(request);
    const { response, body } = await client.getJson('/api/data-provider/', true);

    expect(response.status()).toBe(200);
    expect(Array.isArray(body)).toBe(true);
  });

  test('GET /api/occupancy/ returns list when authenticated', async ({ request }) => {
    const client = new ApiClient(request);
    const { response, body } = await client.getJson('/api/occupancy/', true);

    expect(response.status()).toBe(200);
    expect(Array.isArray(body)).toBe(true);
  });

  test('GET /api/progression/ returns list when authenticated', async ({ request }) => {
    const client = new ApiClient(request);
    const { response, body } = await client.getJson('/api/progression/', true);

    expect(response.status()).toBe(200);
    expect(Array.isArray(body)).toBe(true);
  });

  test('GET /api/equipment/ returns list when authenticated', async ({ request }) => {
    const client = new ApiClient(request);
    const { response, body } = await client.getJson('/api/equipment/', true);

    expect(response.status()).toBe(200);
    expect(Array.isArray(body)).toBe(true);
  });
});
