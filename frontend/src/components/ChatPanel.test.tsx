import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ChatPanel } from "./ChatPanel";
import type { ChatResponse } from "@/types/fleet";

function mockChat(body: ChatResponse, deferred = false) {
  let resolve!: () => void;
  const gate = new Promise<void>((r) => (resolve = r));
  const fetchMock = vi.fn().mockImplementation(async () => {
    if (deferred) await gate;
    return { ok: true, status: 200, statusText: "OK", json: async () => body };
  });
  vi.stubGlobal("fetch", fetchMock);
  return { fetchMock, resolve };
}

async function send(text: string) {
  await userEvent.type(screen.getByLabelText("Message the flight director"), text);
  await userEvent.click(screen.getByRole("button", { name: "Send" }));
}

describe("ChatPanel", () => {
  beforeEach(() => vi.unstubAllGlobals());

  it("renders the operator message and the assistant reply", async () => {
    const { fetchMock } = mockChat({ message: "Fleet is healthy." });
    render(<ChatPanel onActionsExecuted={vi.fn()} />);

    await send("status?");

    expect(await screen.findByText("Fleet is healthy.")).toBeInTheDocument();
    expect(screen.getByText("status?")).toBeInTheDocument();
    const [path, init] = fetchMock.mock.calls[0];
    expect(path).toBe("/api/chat");
    expect(JSON.parse(init.body)).toEqual({ message: "status?" });
  });

  it("shows a loading indicator while the flight director responds", async () => {
    const { resolve } = mockChat({ message: "Done." }, true);
    render(<ChatPanel onActionsExecuted={vi.fn()} />);

    await send("dispatch a drone");

    expect(screen.getByText("Flight director is thinking…")).toBeInTheDocument();
    resolve();
    await waitFor(() =>
      expect(screen.queryByText("Flight director is thinking…")).not.toBeInTheDocument(),
    );
  });

  it("renders executed missions and roster changes inline", async () => {
    mockChat({
      message: "Dispatched.",
      missions: [{ drone_id: "FALCON-03", action: "launch", zone: "Riverside", distance_km: 4.2 }],
      roster_changes: [{ drone_id: "FALCON-11", action: "add" }],
    });
    render(<ChatPanel onActionsExecuted={vi.fn()} />);

    await send("send a drone to Riverside");

    expect(await screen.findByText("LAUNCH FALCON-03 → Riverside (4.2 km)")).toBeInTheDocument();
    expect(screen.getByText("ADD FALCON-11")).toBeInTheDocument();
  });
});
