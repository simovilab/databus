/**
 * Journey: Django Admin
 * Validates admin login, redirect behavior, and list views for key models.
 */
import { test, expect } from '@playwright/test';
import { AdminPage } from '../pages/admin.page';

test.describe('Django Admin', () => {
  test('GET /admin/ redirects unauthenticated user to login page', async ({ page }) => {
    const response = await page.goto('/admin/');
    // Django admin redirects to /admin/login/
    expect(page.url()).toContain('/admin/login/');
    await expect(page.locator('#id_username')).toBeVisible();
    await expect(page.locator('#id_password')).toBeVisible();
  });

  test('Admin login with valid credentials succeeds', async ({ page }) => {
    const adminPage = new AdminPage(page);
    await adminPage.login('admin', 'admin');

    // Should land on admin index after login
    expect(page.url()).toContain('/admin/');
    await adminPage.expectLoggedIn();
    await expect(page.locator('#site-name')).toBeVisible();
  });

  test('Admin login with invalid credentials shows error', async ({ page }) => {
    await page.goto('/admin/login/');
    await page.locator('#id_username').fill('wrong_user');
    await page.locator('#id_password').fill('wrong_pass');
    await page.locator('[type="submit"]').click();

    // Should stay on login page with error message
    expect(page.url()).toContain('/admin/login/');
    await expect(page.locator('.errornote')).toBeVisible();
  });

  test('Admin index lists registered apps after login', async ({ page }) => {
    const adminPage = new AdminPage(page);
    await adminPage.login('admin', 'admin');

    await page.goto('/admin/');
    await expect(page.locator('#content-main')).toBeVisible();
    // Django admin groups models by app
    const appModules = page.locator('.app-gtfs, .app-feed, .module');
    await expect(appModules.first()).toBeVisible();
  });

  test('GTFS Agency list view is accessible', async ({ page }) => {
    const adminPage = new AdminPage(page);
    await adminPage.login('admin', 'admin');
    await adminPage.navigateToModelList('gtfs', 'agency');

    await expect(page.locator('h1, #content h1')).toBeVisible();
    // The change list container should be present (even if empty)
    await expect(page.locator('#changelist')).toBeVisible();
  });

  test('Feed Company list view is accessible', async ({ page }) => {
    const adminPage = new AdminPage(page);
    await adminPage.login('admin', 'admin');
    await adminPage.navigateToModelList('feed', 'company');

    await expect(page.locator('h1, #content h1')).toBeVisible();
  });

  test('Admin logout works correctly', async ({ page }) => {
    const adminPage = new AdminPage(page);
    await adminPage.login('admin', 'admin');

    // Django >= 5.x uses GET /admin/logout/ or form-based POST
    await page.goto('/admin/logout/');
    // After logout, redirected to login or homepage
    await expect(page).toHaveURL(/login|\/$/);
  });
});
