import { defineConfig, devices } from "@playwright/test";

/**
 * Playwright E2E configuration.
 *
 * Targets the running stack: frontend at http://localhost:5173,
 * backend API at http://localhost:8000.
 *
 * Start services first with:  ./run_tests.sh start
 * Then run E2E with:          ./run_tests.sh test-e2e
 */
export default defineConfig({
  globalSetup: "./global-setup.ts",
  testDir: "./tests",
  fullyParallel: false,         // serial to avoid race conditions on shared DB
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  workers: 1,
  reporter: [["list"], ["html", { open: "never" }]],
  timeout: 30_000,

  use: {
    baseURL: process.env.FRONTEND_URL ?? "http://localhost:5173",
    trace: "on-first-retry",
    screenshot: "only-on-failure",
    video: "off",
  },

  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
});
