import { expect, test } from "@playwright/test";

const STREAM = "**/api/stream/telemetry";

test("connection indicator reports a live telemetry stream", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByText("Live", { exact: true })).toBeVisible();
});

test("stream recovers on its own after a dropped connection", async ({ page }) => {
  await page.route(STREAM, (route) => route.abort());
  await page.goto("/");
  await expect(page.getByText("Disconnected", { exact: true })).toBeVisible();

  // EventSource retries by itself; once the route stops failing it reconnects.
  await page.unroute(STREAM);
  await expect(page.getByText("Live", { exact: true })).toBeVisible({ timeout: 30000 });
});
