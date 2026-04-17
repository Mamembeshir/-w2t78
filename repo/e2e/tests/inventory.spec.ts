/**
 * E2E: Inventory module
 *
 * Covers:
 *  - Inventory dashboard renders for inventory manager
 *  - Inventory sub-pages are accessible
 *  - Procurement analyst cannot access inventory routes (RBAC)
 *  - Admin can access inventory dashboard
 */
import { test, expect } from "@playwright/test";
import * as path from "path";

// ---------------------------------------------------------------------------
// Inventory manager — full access
// ---------------------------------------------------------------------------
test.describe("Inventory dashboard", () => {
  test.use({
    storageState: path.join(__dirname, "../.auth/inv_manager.json"),
  });

  test.beforeEach(async ({ page }) => {
    await page.goto("/inventory");
  });

  test("dashboard renders without errors", async ({ page }) => {
    await expect(page).toHaveURL(/\/inventory/, { timeout: 10_000 });
    await expect(page.locator("body")).not.toContainText("Something went wrong");
    await expect(page.locator("body")).not.toContainText("error");
  });

  test("can navigate to inventory search", async ({ page }) => {
    await page.goto("/inventory/search");
    await expect(page.locator("body")).not.toContainText("Something went wrong");
    await expect(page.locator("body")).not.toContainText("404");
  });

  test("can navigate to receive stock page", async ({ page }) => {
    await page.goto("/inventory/receive");
    await expect(page.locator("body")).not.toContainText("Something went wrong");
  });

  test("can navigate to issue stock page", async ({ page }) => {
    await page.goto("/inventory/issue");
    await expect(page.locator("body")).not.toContainText("Something went wrong");
  });

  test("can navigate to transfer page", async ({ page }) => {
    await page.goto("/inventory/transfer");
    await expect(page.locator("body")).not.toContainText("Something went wrong");
  });

  test("can navigate to cycle count page", async ({ page }) => {
    await page.goto("/inventory/cycle");
    await expect(page.locator("body")).not.toContainText("Something went wrong");
  });
});

// ---------------------------------------------------------------------------
// RBAC — analyst must not access /inventory
// ---------------------------------------------------------------------------
test.describe("Inventory RBAC - analyst", () => {
  test.use({
    storageState: path.join(__dirname, "../.auth/analyst.json"),
  });

  test("procurement analyst is redirected away from /inventory", async ({
    page,
  }) => {
    await page.goto("/inventory");
    await expect(page).not.toHaveURL(/\/inventory$/, { timeout: 6_000 });
  });
});

// ---------------------------------------------------------------------------
// Admin — can access inventory
// ---------------------------------------------------------------------------
test.describe("Inventory as admin", () => {
  test.use({
    storageState: path.join(__dirname, "../.auth/admin.json"),
  });

  test("admin can access inventory dashboard", async ({ page }) => {
    await page.goto("/inventory");
    await expect(page.locator("body")).not.toContainText("Something went wrong");
  });
});
