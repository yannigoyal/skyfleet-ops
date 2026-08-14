import { test, expect } from "@playwright/test";
import { getRoster, pickIdleDrone, restoreFleetState } from "./helpers";

// TEST-04 scenario 4: the fleet heatmap, energy-budget chart, and per-row
// sparklines are proven to receive and render real fleet data, using
// structural assertions tied to the elements those components actually
// emit (D-03 rules out screenshot comparison — cross-environment font/GPU
// rendering makes pixel diffs flaky, and a flaky visual assertion gets its
// threshold widened until it stops detecting anything).

const ZONE = "Riverside";
const DISTANCE_KM = 1.5;

let launchedDroneId: string | null = null;

test.afterEach(async ({ request }) => {
  if (launchedDroneId) {
    await restoreFleetState(request, { launchedDroneIds: [launchedDroneId] });
    launchedDroneId = null;
  }
});

test("heatmap, budget chart, and sparklines render real fleet data structurally", async ({
  page,
  request,
}) => {
  const roster = await getRoster(request);
  const rosterIds = roster.drones.map((drone) => drone.drone_id);

  await page.goto("/");

  // Heatmap. Count SVG rects by the three battery-band fill values the cell
  // renderer actually emits, rather than every `rect` on the page — the
  // line chart and sparklines also render inside SVG surfaces, so a bare
  // `rect` count would drift with unrelated chart internals, while a
  // fill-matched count can only be satisfied by cells the heatmap's own
  // colour mapping produced.
  await expect(page.getByText("Fleet Heatmap", { exact: true })).toBeVisible({ timeout: 15_000 });
  const heatmapCells = page.locator(
    'rect[fill="#34d399"], rect[fill="#f2a900"], rect[fill="#f87171"]',
  );
  await expect(heatmapCells).toHaveCount(rosterIds.length, { timeout: 15_000 });

  // At least one cell carries both its drone id and a battery percentage as
  // SVG text — the non-colour cue a colour-blind dispatcher depends on, and
  // this spec is the end-to-end witness for that Phase 3 prohibition. An
  // active mission from an earlier spec can enlarge one cell and shrink the
  // rest below the label-visibility threshold, so this asserts "at least
  // one" rather than "all ten" (see this plan's flagged assumption).
  const idPattern = new RegExp(`^(${rosterIds.join("|")})$`);
  const cellWithIdLabel = page
    .locator("g")
    .filter({ has: page.locator("text", { hasText: idPattern }) });
  const cellWithBothLabels = cellWithIdLabel.filter({
    has: page.locator("text", { hasText: /%$/ }),
  });
  await expect(cellWithBothLabels.first()).toBeVisible({ timeout: 15_000 });

  // Budget chart. Do not assume history exists; make it. Launching and
  // recalling a mission each write a budget_snapshots row immediately (the
  // scheduler's 30s periodic snapshot is not the only writer), so this spec
  // never depends on whatever earlier specs happened to leave behind.
  const droneId = await pickIdleDrone(request);
  const launchRes = await request.post("/api/fleet/missions", {
    data: { drone_id: droneId, zone: ZONE, distance_km: DISTANCE_KM },
  });
  expect(launchRes.status()).toBe(201);
  launchedDroneId = droneId;
  const recallRes = await request.delete(`/api/fleet/missions/${droneId}`);
  expect(recallRes.status()).toBe(200);
  launchedDroneId = null;

  await expect(page.getByText("Energy Budget", { exact: true })).toBeVisible({ timeout: 15_000 });

  // Assert the line exists rather than asserting the empty-state text is
  // gone — a present line is positive evidence the data reached the chart,
  // whereas an absent empty state would also be satisfied by an error
  // state. Wide timeout: this chart is on its own independent 5-second
  // history poll, unlike the header/missions-table which refetch
  // immediately after dispatch.
  await expect(page.locator("path.recharts-line-curve")).toBeVisible({ timeout: 15_000 });

  // Sparklines. The sparkline renders a plain fixed-size placeholder div
  // until the first telemetry point arrives and only then mounts a chart,
  // so an svg per row is exactly the signal that client-side history
  // accumulation is working. Scope to the roster table specifically (its
  // unique "Battery Trend" column header) to avoid counting SVGs from the
  // heatmap or budget chart.
  const rosterTableBody = page
    .locator("table", { has: page.getByText("Battery Trend", { exact: true }) })
    .locator("tbody");
  await expect(async () => {
    const svgCount = await rosterTableBody.locator("svg").count();
    expect(svgCount).toBeGreaterThanOrEqual(rosterIds.length);
  }).toPass({ timeout: 15_000, intervals: [500] });
});
