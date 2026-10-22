// End-to-end smoke tests (ROADMAP 6.3.7) against a running CreditCast: the API
// serving the built cockpit, with trained models. Desktop and phone sizes.
//
//   E2E_BASE_URL=http://127.0.0.1:8000 npx playwright test
//   PW_CHANNEL=msedge ...   # use an installed Edge/Chrome instead of a download
import { defineConfig } from "@playwright/test";

const channel = process.env.PW_CHANNEL || undefined;

export default defineConfig({
  testDir: "./e2e",
  timeout: 45_000,
  expect: { timeout: 10_000 },
  retries: process.env.CI ? 1 : 0,
  // Many browsers launching at once overloads small machines (seen locally).
  workers: process.env.CI ? 2 : 4,
  reporter: process.env.CI ? [["list"], ["html", { open: "never" }]] : "list",
  use: {
    baseURL: process.env.E2E_BASE_URL || "http://127.0.0.1:8000",
    channel,
    trace: "on-first-retry",
  },
  projects: [
    { name: "desktop", use: { viewport: { width: 1280, height: 800 } } },
    { name: "phone", use: { viewport: { width: 375, height: 812 }, isMobile: true, hasTouch: true } },
  ],
});
