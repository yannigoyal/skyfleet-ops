import { expect, test, type Page } from "@playwright/test";
import { getFleet, pickLaunchableDrone, recallIfActive } from "../support/fleet";

const ZONE = "Riverside";
const DISTANCE_KM = 4;
const ENERGY_COST_KWH = 3.2; // 0.8 kWh per km

async function remainingKwh(page: Page): Promise<number> {
  const text = await page.getByRole("banner").getByText(/kWh/).textContent();
  return Number.parseFloat(text ?? "");
}

async function dispatch(page: Page, droneId: string, action: "Launch" | "Recall") {
  await page.getByLabel("Drone", { exact: true }).fill(droneId);
  if (action === "Launch") {
    await page.getByLabel("Zone").fill(ZONE);
    await page.getByLabel("Distance km").fill(String(DISTANCE_KM));
  }
  await page.getByRole("button", { name: action }).click();
}

test("launching a mission spends budget and lists the mission", async ({ page, request }) => {
  const droneId = await pickLaunchableDrone(request);
  const budgetBefore = (await getFleet(request)).remaining_kwh;

  await page.goto("/");
  await expect.poll(() => remainingKwh(page)).toBe(budgetBefore);
  await dispatch(page, droneId, "Launch");

  const missionRow = page
    .getByTestId("missions-table")
    .getByRole("row")
    .filter({ hasText: droneId });
  await expect(missionRow).toContainText(ZONE);
  await expect(missionRow).toContainText(`${ENERGY_COST_KWH.toFixed(1)} kWh`);
  await expect(missionRow).toContainText("en route");

  await expect.poll(() => remainingKwh(page)).toBeCloseTo(budgetBefore - ENERGY_COST_KWH, 1);
  expect((await getFleet(request)).missions.map((m) => m.drone_id)).toContain(droneId);

  await recallIfActive(request, droneId);
});

test("recalling a drone clears its active mission", async ({ page, request }) => {
  const droneId = await pickLaunchableDrone(request);
  const launch = await request.post("/api/fleet/missions", {
    data: { drone_id: droneId, zone: ZONE, distance_km: DISTANCE_KM },
  });
  expect(launch.status()).toBe(201);

  await page.goto("/");
  const missionRow = page
    .getByTestId("missions-table")
    .getByRole("row")
    .filter({ hasText: droneId });
  await expect(missionRow).toBeVisible();

  await page.getByTestId("fleet-roster").getByRole("row").filter({ hasText: droneId }).click();
  await expect(page.getByText(`${DISTANCE_KM.toFixed(1)} km`).first()).toBeVisible();

  await dispatch(page, droneId, "Recall");

  await expect(missionRow).toHaveCount(0);
  await expect(page.getByText("No active mission.")).toBeVisible();
  expect((await getFleet(request)).missions.map((m) => m.drone_id)).not.toContain(droneId);
});
