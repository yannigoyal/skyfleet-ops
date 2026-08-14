import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./specs",
  // Seven specs share one app container holding one energy budget, one
  // roster, and one mission list. Parallel workers would interleave
  // mutations and produce failures that look like product bugs but are
  // test-harness artifacts (TEST-04 concurrency criterion).
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
