import { type Page, expect } from '@playwright/test';

export class AdminPage {
  readonly page: Page;

  constructor(page: Page) {
    this.page = page;
  }

  async goto() {
    await this.page.goto('/admin/');
  }

  async login(username: string, password: string) {
    await this.page.goto('/admin/login/');
    await this.page.locator('#id_username').fill(username);
    await this.page.locator('#id_password').fill(password);
    await this.page.locator('[type="submit"]').click();
    await this.page.waitForURL('**/admin/**');
  }

  async expectLoggedIn() {
    await expect(this.page.locator('#header')).toBeVisible();
    await expect(this.page.locator('#user-tools')).toContainText('admin');
  }

  async navigateToModelList(appLabel: string, modelName: string) {
    await this.page.goto(`/admin/${appLabel}/${modelName}/`);
    await expect(this.page.locator('#content')).toBeVisible();
  }
}
