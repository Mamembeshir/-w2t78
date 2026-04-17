import { type Page } from "@playwright/test";

/** Seed credentials created by `python manage.py seed_users`. */
export const USERS = {
  admin: { username: "admin", password: "Wh@reH0use!" },
  inv_manager: { username: "inv_manager", password: "St0ck!Ctrl99" },
  analyst: { username: "analyst", password: "Pr0cur3!Analy" },
} as const;

const API_BASE = process.env.API_URL ?? "http://localhost:8000";

/**
 * Log in by calling the backend API directly, then injecting the JWT tokens
 * into localStorage so the React AuthContext picks them up on the next
 * navigation. This is faster and more reliable than submitting the UI form,
 * which can race against React's re-render and the router redirect chain.
 *
 * localStorage keys must match src/lib/api.ts: "access_token" / "refresh_token".
 */
export async function loginAs(
  page: Page,
  role: keyof typeof USERS,
): Promise<void> {
  const { username, password } = USERS[role];

  // 1. Obtain tokens from the backend (runs in the test-runner process, not
  //    the browser, so there are no CORS concerns).
  const response = await page.request.post(`${API_BASE}/api/auth/login/`, {
    data: { username, password },
  });

  if (!response.ok()) {
    throw new Error(
      `Login API returned ${response.status()} for user '${username}': ${await response.text()}`,
    );
  }

  const { access, refresh } = await response.json();

  // 2. Load the app's origin so we can write to its localStorage.
  await page.goto("/login");

  // 3. Inject tokens — AuthContext reads these on the next full navigation.
  await page.evaluate(
    ([accessToken, refreshToken]) => {
      localStorage.setItem("access_token", accessToken);
      localStorage.setItem("refresh_token", refreshToken);
    },
    [access, refresh],
  );

  // 4. Navigate to root. AuthContext calls /api/auth/me/, sets user state,
  //    then the router redirects to the role-appropriate dashboard.
  await page.goto("/");
  await page.waitForURL((url) => !url.pathname.includes("/login"), {
    timeout: 15_000,
  });
}

/**
 * Clear auth state (wipes localStorage tokens and navigates to /login).
 */
export async function logout(page: Page): Promise<void> {
  await page.evaluate(() => {
    localStorage.removeItem("access_token");
    localStorage.removeItem("refresh_token");
  });
  await page.goto("/login");
}
