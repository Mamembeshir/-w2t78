/**
 * E2E: Admin module
 *
 * Covers:
 *  - Admin dashboard renders for admin user
 *  - User management, audit log, and system settings pages are accessible
 *  - Non-admin users cannot access /admin routes (RBAC)
 */
import { test, expect } from "@playwright/test";
import * as path from "path";

// ---------------------------------------------------------------------------
// Admin user — full access
// ---------------------------------------------------------------------------
test.describe("Admin dashboard", () => {
  test.use({
    storageState: path.join(__dirname, ".auth/admin.json"),
  });

  test.beforeEach(async ({ page }) => {
    await page.goto("/admin");
  });

  test("admin dashboard renders without errors", async ({ page }) => {
    await expect(page.locator("body")).not.toContainText("Something went wrong");
    await expect(page.locator("body")).not.toContainText("404");
  });

  test("can navigate to user management", async ({ page }) => {
    await page.goto("/admin/users");
    await expect(page.locator("body")).not.toContainText("Something went wrong");
  });

  test("can navigate to audit log", async ({ page }) => {
    await page.goto("/admin/audit");
    await expect(page.locator("body")).not.toContainText("Something went wrong");
  });

  test("can navigate to system settings", async ({ page }) => {
    await page.goto("/admin/settings");
    await expect(page.locator("body")).not.toContainText("Something went wrong");
  });
});

// ---------------------------------------------------------------------------
// RBAC — inventory manager must not access /admin
// ---------------------------------------------------------------------------
test.describe("Admin RBAC - inventory manager", () => {
  test.use({
    storageState: path.join(__dirname, ".auth/inv_manager.json"),
  });

  test("inventory manager is redirected away from /admin", async ({ page }) => {
    await page.goto("/admin");
    await expect(page).not.toHaveURL(/\/admin$/, { timeout: 6_000 });
  });
});

// ---------------------------------------------------------------------------
// RBAC — analyst must not access /admin
// ---------------------------------------------------------------------------
test.describe("Admin RBAC - analyst", () => {
  test.use({
    storageState: path.join(__dirname, ".auth/analyst.json"),
  });

  test("analyst is redirected away from /admin", async ({ page }) => {
    await page.goto("/admin");
    await expect(page).not.toHaveURL(/\/admin$/, { timeout: 6_000 });
  });
});
