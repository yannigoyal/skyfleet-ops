import { test, expect } from "@playwright/test";
import { restoreFleetState } from "./helpers";

// TEST-04 scenario 2: a drone added via POST /api/roster appears in the
// fleet roster panel and the dispatch bar's drone selector; removing it via
// DELETE /api/roster/{drone_id} makes it disappear from both. There is no
// manual "Add Drone" / "Remove Drone" UI control anywhere in the frontend —
// the only roster call site is a GET inside FleetOpsProvider — so the
// mutation is driven through the API and the effect is observed in the UI.

const DRONE_ID = "FALCON-11";

test.afterEach(async ({ request }) => {
  // Runs even when the spec body fails, so a mid-spec failure never leaves
  // an eleventh drone behind to break fresh-start.spec.ts's ten-row
  // assertion on the next run.
  await restoreFleetState(request, { addedDroneIds: [DRONE_ID] });
});

test("adding and removing a drone updates both the roster panel and the dispatch selector", async ({
  page,
  request,
}) => {
  const addRes = await request.post("/api/roster", { data: { drone_id: DRONE_ID } });
  expect(addRes.status()).toBe(201);

  await page.goto("/");

  // The roster panel renders only from SSE snapshots, so this row appearing
  // proves the service registered the drone with the telemetry source, not
  // merely that a database row was written.
  await expect(page.getByText(DRONE_ID, { exact: true })).toBeVisible({ timeout: 15_000 });

  // The dispatch bar's drone selector is fed by FleetOpsProvider's separate
  // 5-second roster poll, not the stream — poll for it rather than assuming
  // it updates on the same tick as the roster panel.
  const droneOption = page.locator("select").locator(`option[value="${DRONE_ID}"]`);
  await expect(droneOption).toHaveCount(1, { timeout: 10_000 });

  const removeRes = await request.delete(`/api/roster/${DRONE_ID}`);
  expect(removeRes.status()).toBe(204);

  await page.reload();

  // The disappearance assertion is the half of this scenario with actual
  // failure power — an add-only test would pass against a broken delete path.
  await expect(page.getByText(DRONE_ID, { exact: true })).not.toBeVisible({ timeout: 10_000 });
  await expect(page.locator("select").locator(`option[value="${DRONE_ID}"]`)).toHaveCount(0);
});
