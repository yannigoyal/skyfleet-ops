import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./specs",
  // The suite mutates one shared backend (budget, roster, missions), so tests
  // run one at a time rather than racing each other for fleet state.
  fullyParallel: false,
  workers: 1,
  retries: process.env.CI ? 2 : 0,
  reporter: [["html", { outputFolder: "playwright-report", open: "never" }]],
  use: {
    baseURL: process.env.BASE_URL ?? "http://localhost:8000",
    trace: "on-first-retry",
  },
  projects: [
    { name: "chromium", use: { ...devices["Desktop Chrome"] } },
  ],
});
