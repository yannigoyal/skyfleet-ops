import { expect, test } from "@playwright/test";
import { removeFromRosterIfPresent } from "../support/fleet";

const NEW_DRONE = "FALCON-77";

test.afterEach(async ({ request }) => {
  await removeFromRosterIfPresent(request, NEW_DRONE);
});

test("add and remove a drone from the roster", async ({ page }) => {
  await page.goto("/");
  const manager = page.getByTestId("roster-manager");
  const roster = page.getByTestId("fleet-roster");

  await manager.getByLabel("New drone ID").fill(NEW_DRONE);
  await manager.getByRole("button", { name: "Add" }).click();

  await expect(manager.getByText(NEW_DRONE)).toBeVisible();
  // The telemetry source picks the new drone up, so it also joins the live grid.
  await expect(roster.getByRole("cell", { name: NEW_DRONE, exact: true })).toBeVisible();

  await manager.getByRole("button", { name: `Remove ${NEW_DRONE}` }).click();

  await expect(manager.getByText(NEW_DRONE)).toHaveCount(0);
  await expect(roster.getByRole("cell", { name: NEW_DRONE, exact: true })).toHaveCount(0);
});
