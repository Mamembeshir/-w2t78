/**
 * E2E: Crawling module
 *
 * Covers:
 *  - Crawling dashboard renders for analyst
 *  - Crawling sub-pages are accessible
 *  - Inventory manager cannot access crawling routes (RBAC)
 *  - Admin can access crawling dashboard
 */
import { test, expect } from "@playwright/test";
import * as path from "path";

// ---------------------------------------------------------------------------
// Analyst — full access
// ---------------------------------------------------------------------------
test.describe("Crawling dashboard", () => {
  test.use({
    storageState: path.join(__dirname, ".auth/analyst.json"),
  });

  test.beforeEach(async ({ page }) => {
    await page.goto("/crawling");
  });

  test("dashboard renders without errors", async ({ page }) => {
    await expect(page).toHaveURL(/\/crawling/, { timeout: 10_000 });
    await expect(page.locator("body")).not.toContainText("Something went wrong");
  });

  test("can navigate to sources page", async ({ page }) => {
    await page.goto("/crawling/sources");
    await expect(page.locator("body")).not.toContainText("Something went wrong");
    await expect(page.locator("body")).not.toContainText("404");
  });

  test("can navigate to task monitor page", async ({ page }) => {
    await page.goto("/crawling/tasks");
    await expect(page.locator("body")).not.toContainText("Something went wrong");
  });

  test("can navigate to rule version editor", async ({ page }) => {
    await page.goto("/crawling/rules");
    await expect(page.locator("body")).not.toContainText("Something went wrong");
  });

  test("can navigate to request debugger", async ({ page }) => {
    await page.goto("/crawling/debugger");
    await expect(page.locator("body")).not.toContainText("Something went wrong");
  });
});

// ---------------------------------------------------------------------------
// RBAC — inventory manager must not access /crawling
// ---------------------------------------------------------------------------
test.describe("Crawling RBAC - inventory manager", () => {
  test.use({
    storageState: path.join(__dirname, ".auth/inv_manager.json"),
  });

  test("inventory manager is redirected away from /crawling", async ({
    page,
  }) => {
    await page.goto("/crawling");
    await expect(page).not.toHaveURL(/\/crawling$/, { timeout: 6_000 });
  });
});

// ---------------------------------------------------------------------------
// Admin — can access crawling
// ---------------------------------------------------------------------------
test.describe("Crawling as admin", () => {
  test.use({
    storageState: path.join(__dirname, ".auth/admin.json"),
  });

  test("admin can access crawling dashboard", async ({ page }) => {
    await page.goto("/crawling");
    await expect(page.locator("body")).not.toContainText("Something went wrong");
  });
});
