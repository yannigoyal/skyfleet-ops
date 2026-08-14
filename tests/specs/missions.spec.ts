import { test, expect } from "@playwright/test";
import { getFleet, pickIdleDrone, readHeaderRemainingKwh, restoreFleetState } from "./helpers";

// TEST-04 scenario 3: launching a mission from the dispatch bar adds an En
// Route row to the missions table and reduces the header's remaining kWh;
// recalling it moves that mission to Recalled and returns the active
// mission count to its pre-test value.

const ZONE = "Riverside";
const DISTANCE_KM = "1.5";

let launchedDroneId: string | null = null;

test.afterEach(async ({ request }) => {
  // Runs even when the spec body fails, so a mid-spec failure never leaves
  // an en-route mission holding budget for every subsequent run. Recall may
  // legitimately fail if the background delivery scheduler already
  // completed the mission — restoreFleetState tolerates that.
  if (launchedDroneId) {
    await restoreFleetState(request, { launchedDroneIds: [launchedDroneId] });
    launchedDroneId = null;
  }
});

test("launching and recalling a mission moves budget and mission count and back", async ({
  page,
  request,
}) => {
  // pickIdleDrone rather than a hardcoded id: earlier specs and the mocked
  // chat scenario may already have a drone en route, and launching against
  // a busy drone fails with an error that looks like a product bug.
  const droneId = await pickIdleDrone(request);

  const fleetBefore = await getFleet(request);
  const missionCountBefore = fleetBefore.active_mission_count;

  await page.goto("/");
  const remainingBefore = await readHeaderRemainingKwh(page);

  await page.getByLabel("Drone").selectOption(droneId);
  await page.getByLabel("Zone").fill(ZONE);
  await page.getByLabel("Distance (km)").fill(DISTANCE_KM);
  await page.getByRole("button", { name: "Launch Mission" }).click();
  launchedDroneId = droneId;

  // The missions table gains a row carrying both the drone id and the zone
  // together with the En Route label — a row-count assertion alone would
  // pass on any mission, including one another spec created. Scope the row
  // search to the Missions panel specifically: the roster panel also has a
  // <tr> containing this drone id, and an unscoped locator would match both,
  // tripping Playwright's strict mode.
  const missionsPanel = page.getByText("Missions", { exact: true }).locator("..");
  const missionRow = missionsPanel.locator("tr", {
    has: page.getByText(droneId, { exact: true }),
  });
  await expect(missionRow).toContainText(ZONE, { timeout: 10_000 });
  await expect(missionRow).toContainText("En Route");

  // The header updates immediately via DispatchBar's own refetch() after a
  // successful launch — assert here, not against the budget chart, which
  // polls independently every 5s and would flake.
  await expect(async () => {
    const remainingAfterLaunch = await readHeaderRemainingKwh(page);
    expect(remainingAfterLaunch).toBeLessThan(remainingBefore);
  }).toPass({ timeout: 10_000, intervals: [500] });

  await expect(async () => {
    const fleetAfterLaunch = await getFleet(request);
    expect(fleetAfterLaunch.active_mission_count).toBe(missionCountBefore + 1);
  }).toPass({ timeout: 10_000, intervals: [500] });

  // Recall through the UI: the round trip is what makes this scenario more
  // than a one-way write, and the count returning to its starting value is
  // what proves the recall released the mission instead of adding a second
  // record.
  await page.getByRole("button", { name: "Recall" }).click();

  await expect(missionRow).toContainText("Recalled", { timeout: 10_000 });

  await expect(async () => {
    const fleetAfterRecall = await getFleet(request);
    expect(fleetAfterRecall.active_mission_count).toBe(missionCountBefore);
  }).toPass({ timeout: 10_000, intervals: [500] });
});
