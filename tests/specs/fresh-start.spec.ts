import { expect, test } from "@playwright/test";
import { getFleet } from "../support/fleet";

const DEFAULT_FLEET = Array.from({ length: 10 }, (_, i) => `FALCON-${String(i + 1).padStart(2, "0")}`);

test("default fleet roster streams in on first load", async ({ page }) => {
  await page.goto("/");
  const roster = page.getByTestId("fleet-roster");

  for (const droneId of DEFAULT_FLEET) {
    await expect(roster.getByRole("cell", { name: droneId, exact: true })).toBeVisible();
  }
});

test("header shows the operator energy budget", async ({ page, request }) => {
  const fleet = await getFleet(request);
  // The 500 kWh allowance is the seeded total; the header renders what is left
  // of it, which earlier tests in the run may already have spent down.
  expect(fleet.energy_budget_kwh).toBe(500);

  await page.goto("/");
  await expect(page.getByText(`${fleet.remaining_kwh.toFixed(1)} kWh`)).toBeVisible();
});

test("telemetry values keep updating after load", async ({ page }) => {
  await page.goto("/");
  const batteryCell = page
    .getByTestId("fleet-roster")
    .getByRole("row")
    .filter({ hasText: "FALCON-01" })
    .getByRole("cell")
    .nth(1);

  const first = await batteryCell.textContent();
  await expect.poll(() => batteryCell.textContent(), { timeout: 15000 }).not.toBe(first);
});
