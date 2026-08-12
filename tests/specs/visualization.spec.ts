import { expect, test } from "@playwright/test";
import { pickLaunchableDrone, recallIfActive } from "../support/fleet";

const BATTERY_FILLS = ["#dc2626", "#f2a900", "#10b981"];

test("heatmap renders a tile per drone, colored by battery health", async ({ page }) => {
  await page.goto("/");
  const tiles = page.getByTestId("fleet-heatmap").locator("svg rect");

  await expect.poll(() => tiles.count()).toBeGreaterThanOrEqual(10);

  const fills = await tiles.evaluateAll((nodes) =>
    nodes.map((node) => node.getAttribute("fill")),
  );
  for (const fill of fills) {
    expect(BATTERY_FILLS).toContain(fill);
  }
});

test("budget chart plots snapshots once the budget moves", async ({ page, request }) => {
  const droneId = await pickLaunchableDrone(request);
  // Each launch writes a budget snapshot, so we do not have to wait out the
  // backend's 30s snapshot loop for the chart to have data.
  await request.post("/api/fleet/missions", {
    data: { drone_id: droneId, zone: "Riverside", distance_km: 4 },
  });

  await page.goto("/");
  const chart = page.getByTestId("energy-budget-chart");

  await expect(chart.getByText("No budget snapshots yet.")).toHaveCount(0);
  await expect(chart.locator("svg")).toBeVisible();
  await expect.poll(() => chart.locator(".recharts-cartesian-axis-tick").count()).toBeGreaterThan(0);

  await recallIfActive(request, droneId);
});
