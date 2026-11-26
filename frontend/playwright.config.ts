import { defineConfig, devices } from "@playwright/test";

const isCI = Boolean(process.env.CI);
const localBaseURL = "http://127.0.0.1:3100";

// Outside CI, E2E keeps its documented behavior: it targets E2E_BASE_URL or the
// deployed site. In CI, serve the locally built revision so the reviewed code
// is tested rather than a possibly stale deployment.
const baseURL = isCI ? localBaseURL : process.env.E2E_BASE_URL || "https://aqi.akashg.me";

export default defineConfig({
  testDir: "./tests/e2e",
  fullyParallel: true,
  forbidOnly: isCI,
  retries: isCI ? 2 : 0,
  reporter: "list",
  use: {
    ...devices["Desktop Chrome"],
    baseURL,
    trace: "on-first-retry",
  },
  ...(isCI
    ? {
        webServer: {
          command: "npm run start -- --port 3100",
          url: localBaseURL,
          reuseExistingServer: !process.env.CI,
          timeout: 120_000,
          env: {
            // When no backend is configured, fail proxy calls fast instead of
            // hanging; the smoke suite checks the UI, not live observations.
            BACKEND_URL: process.env.BACKEND_URL || "http://127.0.0.1:9",
          },
        },
      }
    : {}),
});
