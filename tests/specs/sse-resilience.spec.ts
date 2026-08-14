import { test, expect } from "@playwright/test";

// TEST-04 scenario 6: a dropped telemetry connection surfaces on the
// connection indicator, and the running client heals on its own —
// through the native EventSource retry plus the server's `retry: 1000`
// directive — without operator intervention and without this spec
// standing a page reload in for the recovery it claims to prove.

const STREAM_PATTERN = "**/api/stream/telemetry";

test("telemetry stream disconnects and reconnects without a reload", async ({ page, context }) => {
  await page.goto("/");
  await expect(page.getByText("Live", { exact: true })).toBeVisible({ timeout: 15_000 });

  // Scoped to the stream URL alone. A blanket context.setOffline() would
  // also break the two unrelated 5-second polls (FleetOpsProvider's fleet
  // poll, EnergyBudgetChart's history poll) during the same window, so a
  // failure could originate anywhere and this assertion would no longer be
  // specifically about SSE.
  await context.route(STREAM_PATTERN, (route) => route.abort());

  // Route interception applies to new requests, not a stream already in
  // flight, so a reload is required here: it forces a fresh EventSource
  // that fails immediately, exactly how a real network drop presents to a
  // page reloaded during an outage. This reload is legitimate — it happens
  // before the disconnect assertion, not standing in for the recovery half.
  await page.reload();

  await expect(page.getByText("Disconnected", { exact: true })).toBeVisible({ timeout: 15_000 });

  await context.unroute(STREAM_PATTERN);

  // No reload here. A reload would make this assertion prove only that a
  // fresh page load connects — the spec's first assertion already
  // established that. The claim under test is that the already-running
  // client recovers on its own through the native EventSource retry and the
  // server's retry directive; a reload would let a completely broken
  // reconnect path pass. Wide timeout — the browser's own retry backoff
  // governs when the next attempt happens.
  await expect(page.getByText("Live", { exact: true })).toBeVisible({ timeout: 20_000 });
});
