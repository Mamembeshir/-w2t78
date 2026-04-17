/**
 * E2E: Notifications module
 *
 * Covers:
 *  - Inbox page renders for each role
 *  - Subscriptions settings page is accessible
 *  - Unauthenticated access to /notifications redirects to /login
 */
import { test, expect } from "@playwright/test";
import * as path from "path";

// ---------------------------------------------------------------------------
// Admin — can view notifications
// ---------------------------------------------------------------------------
test.describe("Notifications - admin", () => {
  test.use({
    storageState: path.join(__dirname, ".auth/admin.json"),
  });

  test("admin can view notifications inbox", async ({ page }) => {
    await page.goto("/notifications");
    await expect(page.locator("body")).not.toContainText("Something went wrong");
    await expect(page.locator("body")).not.toContainText("404");
  });

  test("can navigate to subscription settings", async ({ page }) => {
    await page.goto("/notifications/settings");
    await expect(page.locator("body")).not.toContainText("Something went wrong");
  });
});

// ---------------------------------------------------------------------------
// Inventory manager — can view notifications
// ---------------------------------------------------------------------------
test.describe("Notifications - inventory manager", () => {
  test.use({
    storageState: path.join(__dirname, ".auth/inv_manager.json"),
  });

  test("inventory manager can view notifications inbox", async ({ page }) => {
    await page.goto("/notifications");
    await expect(page.locator("body")).not.toContainText("Something went wrong");
  });
});

// ---------------------------------------------------------------------------
// Analyst — can view notifications
// ---------------------------------------------------------------------------
test.describe("Notifications - analyst", () => {
  test.use({
    storageState: path.join(__dirname, ".auth/analyst.json"),
  });

  test("analyst can view notifications inbox", async ({ page }) => {
    await page.goto("/notifications");
    await expect(page.locator("body")).not.toContainText("Something went wrong");
  });
});

// ---------------------------------------------------------------------------
// Unauthenticated guard
// ---------------------------------------------------------------------------
test.describe("Notifications auth guard", () => {
  test("unauthenticated access to /notifications redirects to login", async ({
    page,
  }) => {
    await page.goto("/notifications");
    await expect(page).toHaveURL(/\/login/, { timeout: 6_000 });
  });
});
