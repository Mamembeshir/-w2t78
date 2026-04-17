/**
 * E2E: Authentication flows
 *
 * Covers:
 *  - Login page renders correctly
 *  - Invalid credentials shows error message
 *  - Blank form fields show validation messages
 *  - Each role is redirected to its home dashboard after login
 *  - Unauthenticated access to protected routes redirects to /login
 */
import { test, expect } from "@playwright/test";
import * as path from "path";

// ---------------------------------------------------------------------------
// Login page — no auth required
// ---------------------------------------------------------------------------
test.describe("Login page", () => {
  test("renders sign-in form", async ({ page }) => {
    await page.goto("/login");
    await expect(page.locator("h2")).toContainText("Sign in");
    await expect(page.locator("#username")).toBeVisible();
    await expect(page.locator("#password")).toBeVisible();
    await expect(page.locator('button[type="submit"]')).toBeVisible();
  });

  test("shows error on invalid credentials", async ({ page }) => {
    await page.goto("/login");
    await page.fill("#username", "nobody");
    await page.fill("#password", "wrongpassword");
    await page.click('button[type="submit"]');
    await expect(
      page.locator("text=Invalid username or password"),
    ).toBeVisible({ timeout: 8_000 });
    await expect(page).toHaveURL(/\/login/);
  });

  test("shows client-side error when username is blank", async ({ page }) => {
    await page.goto("/login");
    await page.fill("#password", "anything");
    await page.click('button[type="submit"]');
    await expect(page.locator("text=Username is required")).toBeVisible();
    await expect(page).toHaveURL(/\/login/);
  });

  test("shows client-side error when password is blank", async ({ page }) => {
    await page.goto("/login");
    await page.fill("#username", "admin");
    await page.click('button[type="submit"]');
    await expect(page.locator("text=Password is required")).toBeVisible();
    await expect(page).toHaveURL(/\/login/);
  });
});

// ---------------------------------------------------------------------------
// Role redirect — each role lands on their dashboard (tokens pre-loaded)
// ---------------------------------------------------------------------------
test.describe("Admin home redirect", () => {
  test.use({
    storageState: path.join(__dirname, ".auth/admin.json"),
  });

  test("admin navigating to / lands on /admin", async ({ page }) => {
    await page.goto("/");
    await expect(page).toHaveURL(/\/admin/, { timeout: 10_000 });
  });
});

test.describe("Inventory manager home redirect", () => {
  test.use({
    storageState: path.join(__dirname, ".auth/inv_manager.json"),
  });

  test("inv_manager navigating to / lands on /inventory", async ({ page }) => {
    await page.goto("/");
    await expect(page).toHaveURL(/\/inventory/, { timeout: 10_000 });
  });
});

test.describe("Analyst home redirect", () => {
  test.use({
    storageState: path.join(__dirname, ".auth/analyst.json"),
  });

  test("analyst navigating to / lands on /crawling", async ({ page }) => {
    await page.goto("/");
    await expect(page).toHaveURL(/\/crawling/, { timeout: 10_000 });
  });
});

// ---------------------------------------------------------------------------
// Protected route guard — no auth state
// ---------------------------------------------------------------------------
test.describe("Protected route guard", () => {
  test("unauthenticated user accessing /inventory is redirected to /login", async ({
    page,
  }) => {
    await page.goto("/inventory");
    await expect(page).toHaveURL(/\/login/, { timeout: 8_000 });
  });

  test("unauthenticated user accessing /admin is redirected to /login", async ({
    page,
  }) => {
    await page.goto("/admin");
    await expect(page).toHaveURL(/\/login/, { timeout: 8_000 });
  });
});
