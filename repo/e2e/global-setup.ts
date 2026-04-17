/**
 * Playwright global setup — runs once before any test.
 *
 * Logs in once per role via the backend API, saves the resulting
 * localStorage tokens to a storageState file.  Every test that needs auth
 * just loads the appropriate file — zero repeated login API calls and zero
 * risk of hitting the 5/min rate limit on the login endpoint.
 */
import { chromium, type FullConfig } from "@playwright/test";
import * as fs from "fs";
import * as path from "path";

const API_BASE = process.env.API_URL ?? "http://localhost:8000";
const FRONTEND_BASE = process.env.FRONTEND_URL ?? "http://localhost:5173";

const USERS = {
  admin: { username: "admin", password: "Wh@reH0use!" },
  inv_manager: { username: "inv_manager", password: "St0ck!Ctrl99" },
  analyst: { username: "analyst", password: "Pr0cur3!Analy" },
} as const;

export default async function globalSetup(_config: FullConfig) {
  const stateDir = path.join(__dirname, ".auth");
  fs.mkdirSync(stateDir, { recursive: true });

  const browser = await chromium.launch();

  for (const [role, creds] of Object.entries(USERS)) {
    const context = await browser.newContext();
    const page = await context.newPage();

    // 1. Call the login API directly (avoids the rate-limited UI form).
    const response = await page.request.post(`${API_BASE}/api/auth/login/`, {
      data: { username: creds.username, password: creds.password },
    });

    if (!response.ok()) {
      throw new Error(
        `Global setup: login failed for role '${role}' (${creds.username}): ` +
          `${response.status()} ${await response.text()}`,
      );
    }

    const { access, refresh } = await response.json();

    // 2. Load the app so we can write to its localStorage origin.
    await page.goto(`${FRONTEND_BASE}/login`);

    // 3. Inject tokens — AuthContext reads these on the next navigation.
    await page.evaluate(
      ([accessToken, refreshToken]) => {
        localStorage.setItem("access_token", accessToken);
        localStorage.setItem("refresh_token", refreshToken);
      },
      [access, refresh],
    );

    // 4. Save localStorage + cookies as a storageState file.
    const stateFile = path.join(stateDir, `${role}.json`);
    await context.storageState({ path: stateFile });
    await context.close();

    console.log(`  ✓ Auth state saved for role: ${role} → .auth/${role}.json`);
  }

  await browser.close();
}
