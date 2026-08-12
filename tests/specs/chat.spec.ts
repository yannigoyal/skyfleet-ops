import { expect, test } from "@playwright/test";
import { getFleet } from "../support/fleet";

// Requires LLM_MOCK=true: the mock flight director launches the first idle
// roster drone to Riverside on "launch", and recalls the first active mission
// on "recall" (backend/app/chat/llm.py).

async function send(page: import("@playwright/test").Page, message: string) {
  const chat = page.getByTestId("chat-panel");
  await chat.getByLabel("Message the flight director").fill(message);
  await chat.getByRole("button", { name: "Send" }).click();
  return chat;
}

test("flight director answers a status question without acting", async ({ page, request }) => {
  await page.goto("/");
  const before = await getFleet(request);

  const chat = await send(page, "How is the fleet doing?");

  await expect(chat.getByText(/\[mock\]/)).toBeVisible();
  await expect(chat.getByText(/LAUNCH|RECALL/)).toHaveCount(0);
  expect((await getFleet(request)).active_mission_count).toBe(before.active_mission_count);
});

test("flight director launches and then recalls a mission from chat", async ({ page, request }) => {
  await page.goto("/");
  const before = await getFleet(request);

  const chat = await send(page, "launch a delivery run");

  const confirmation = chat.getByText(/LAUNCH .+ → Riverside \(4 km\)/);
  await expect(confirmation).toBeVisible();

  const droneId = (await confirmation.textContent())?.split(" ")[1] ?? "";
  expect(droneId).not.toBe("");

  await expect
    .poll(() => getFleet(request).then((fleet) => fleet.active_mission_count))
    .toBe(before.active_mission_count + 1);
  await expect(
    page.getByTestId("missions-table").getByRole("row").filter({ hasText: droneId }),
  ).toBeVisible();

  await send(page, "recall that drone");

  await expect(chat.getByText(/RECALL /)).toBeVisible();
  await expect
    .poll(() => getFleet(request).then((fleet) => fleet.active_mission_count))
    .toBe(before.active_mission_count);
});
