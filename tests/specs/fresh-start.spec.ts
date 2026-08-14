import { test, expect } from "@playwright/test";

// TEST-04 scenario 1: on a fresh app container, the console shows the ten
// default FALCON drones, a 500.0 kWh total energy budget in the header, and
// a live telemetry connection. This spec mutates nothing, so it needs no
// restoration — but it asserts on the *total* budget, never the remaining
// figure, so it holds regardless of what other specs ran before it.

const DEFAULT_DRONE_IDS = Array.from(
  { length: 10 },
  (_, i) => `FALCON-${String(i + 1).padStart(2, "0")}`,
);

async function readBattery(page: import("@playwright/test").Page, droneId: string) {
  const row = page.locator("tr", { has: page.getByText(droneId, { exact: true }) });
  return row.locator("td").nth(1).innerText();
}

test("fresh start shows default fleet, 500 kWh budget, and live telemetry", async ({
  page,
  request,
}) => {
  // The default roster is present via the API.
  const rosterRes = await request.get("/api/roster");
  const rosterBody = await rosterRes.json();
  const rosterIds = rosterBody.drones.map((drone: { drone_id: string }) => drone.drone_id);
  for (const droneId of DEFAULT_DRONE_IDS) {
    expect(rosterIds).toContain(droneId);
  }

  await page.goto("/");

  // The roster panel renders exclusively from SSE snapshots, so a visible
  // row for each default drone proves the telemetry stream delivered — this
  // assertion does double duty for the "telemetry is streaming" clause.
  for (const droneId of DEFAULT_DRONE_IDS) {
    await expect(page.getByText(droneId, { exact: true })).toBeVisible({ timeout: 15_000 });
  }

  // The energy budget is 500 kWh — assert on the total from the API and on
  // the header's total figure. Never assert on the remaining figure: that
  // is shared mutable state that earlier specs legitimately reduce.
  const fleetRes = await request.get("/api/fleet");
  const fleetBody = await fleetRes.json();
  expect(fleetBody.energy_budget_kwh).toBe(500.0);
  await expect(page.locator("header")).toContainText("/ 500.0 kWh");

  // The stream is live, not merely rendered once: the connection indicator
  // reads exactly "Live", and a drone's battery percentage changes between
  // two reads. The simulator emits a new reading roughly every 500ms, so a
  // change inside a generous timeout proves the stream is flowing rather
  // than that one snapshot arrived.
  await expect(page.getByText("Live", { exact: true })).toBeVisible({ timeout: 15_000 });

  const initialBattery = await readBattery(page, "FALCON-01");
  await expect(async () => {
    const currentBattery = await readBattery(page, "FALCON-01");
    expect(currentBattery).not.toBe(initialBattery);
  }).toPass({ timeout: 20_000, intervals: [500] });
});
