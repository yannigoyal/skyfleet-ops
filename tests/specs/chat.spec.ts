import { test, expect } from "@playwright/test";
import { getFleet, restoreFleetState } from "./helpers";

// TEST-04 scenario 5: the AI flight director's deterministic mock
// (LLM_MOCK=true) auto-executes a launch and a recall from natural-language
// chat messages, each producing an inline confirmation card and a real
// fleet-state change — the backend's mock_reply() docstring says it exists
// specifically so E2E tests can exercise this path, and this spec is that
// consumer.

let launchedDroneId: string | null = null;

test.afterEach(async ({ request }) => {
  // Tolerant of the mission already being recalled by the spec body — the
  // recall message should have handled it, but a mid-spec failure must
  // never leave a mission holding budget for the next run.
  if (launchedDroneId) {
    await restoreFleetState(request, { launchedDroneIds: [launchedDroneId] });
    launchedDroneId = null;
  }
});

test("mocked flight director launches and recalls a mission through chat", async ({
  page,
  request,
}) => {
  const fleetBefore = await getFleet(request);
  const missionCountBefore = fleetBefore.active_mission_count;

  await page.goto("/");

  const chatInput = page.getByPlaceholder("Ask the flight director...");
  const sendButton = page.getByRole("button", { name: "Send message" });

  // Launch through chat. The mock recognizes "launch" and dispatches the
  // first idle roster drone to Riverside at 4.0 km.
  await chatInput.fill("Launch a drone");
  await sendButton.click();

  const launchCard = page.getByTestId("confirmation-card").first();
  await expect(launchCard).toContainText("LAUNCH", { timeout: 15_000 });
  await expect(launchCard).toContainText("Dispatched");

  // The assistant reply carries the mock's bracketed "[mock]" prefix — this
  // is what distinguishes "the mocked path ran" from "some model answered",
  // and it fails loudly if the harness ever loses LLM_MOCK=true and starts
  // making real, billable, non-deterministic calls.
  await expect(page.getByText(/^\[mock\]/).first()).toBeVisible();

  // The input is interactive again once the reply lands — the durable
  // observable. The loading indicator is mounted only while the request is
  // in flight, and against a local mock that window is too short to observe
  // reliably; asserting on it would add a flake with no coverage value.
  await expect(chatInput).toBeEnabled();

  await expect(async () => {
    const fleetAfterLaunch = await getFleet(request);
    expect(fleetAfterLaunch.active_mission_count).toBe(missionCountBefore + 1);
  }).toPass({ timeout: 10_000, intervals: [500] });

  // Read the drone id off the confirmation card rather than hardcoding one
  // — the mock launches whichever roster drone is first idle, which is not
  // guaranteed across re-runs against a container with leftover state.
  const launchCardText = await launchCard.innerText();
  const droneMatch = launchCardText.match(/LAUNCH\s+(\S+)/);
  if (!droneMatch) {
    throw new Error(`could not read drone id from launch confirmation card: "${launchCardText}"`);
  }
  launchedDroneId = droneMatch[1];

  // Recall through chat. The mock recognizes "recall" and recalls whichever
  // mission is first in the active list.
  await chatInput.fill("Recall the drone");
  await sendButton.click();

  const recallCard = page.getByTestId("confirmation-card").last();
  await expect(recallCard).toContainText("RECALL", { timeout: 15_000 });
  await expect(recallCard).toContainText("Recalled");

  await expect(async () => {
    const fleetAfterRecall = await getFleet(request);
    expect(fleetAfterRecall.active_mission_count).toBe(missionCountBefore);
  }).toPass({ timeout: 10_000, intervals: [500] });
});
