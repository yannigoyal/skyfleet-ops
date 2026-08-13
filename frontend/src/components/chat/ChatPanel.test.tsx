import { render, screen, fireEvent, waitFor, cleanup } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { ChatPanel } from "./ChatPanel";
import { FleetOpsProvider } from "@/lib/FleetOpsProvider";

const EMPTY_ROSTER = { drones: [] };
const EMPTY_FLEET = {
  energy_budget_kwh: 500,
  remaining_kwh: 500,
  active_mission_count: 0,
  missions: [],
};

class NoOpEventSource {
  onopen: (() => void) | null = null;
  onerror: (() => void) | null = null;
  onmessage: ((event: MessageEvent) => void) | null = null;
  close() {}
}

function stubFetch(chatHandler?: (init?: RequestInit) => Promise<Response> | Response) {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = typeof input === "string" ? input : input.toString();
      if (url === "/api/roster") return new Response(JSON.stringify(EMPTY_ROSTER), { status: 200 });
      if (url === "/api/fleet") return new Response(JSON.stringify(EMPTY_FLEET), { status: 200 });
      if (url === "/api/chat" && chatHandler) return chatHandler(init);
      throw new Error(`Unhandled fetch: ${url}`);
    }),
  );
}

function renderPanel() {
  return render(
    <FleetOpsProvider>
      <ChatPanel />
    </FleetOpsProvider>,
  );
}

describe("ChatPanel — docked, collapsible flight-director sidebar", () => {
  beforeEach(() => {
    vi.stubGlobal("EventSource", NoOpEventSource as unknown as typeof EventSource);
    // jsdom has no scrollIntoView implementation; vitest.setup.ts polyfills a
    // no-op globally so the type exists — spy on it here to assert calls.
    vi.spyOn(HTMLElement.prototype, "scrollIntoView").mockImplementation(() => {});
    stubFetch();
  });

  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  it("Test 1 (empty state): with zero turns, renders the exact welcome heading and body, no bubbles", () => {
    renderPanel();

    expect(screen.getByText("Flight Director standing by")).toBeInTheDocument();
    expect(
      screen.getByText(
        'Ask about fleet status or dispatch a mission — e.g. "Launch FALCON-03 to Riverside".',
      ),
    ).toBeInTheDocument();
  });

  it("Test 2: typing a message and submitting calls the hook's send with the typed text", async () => {
    let sentMessage: string | null = null;
    stubFetch((init) => {
      sentMessage = JSON.parse(String(init?.body)).message;
      return new Response(
        JSON.stringify({ message: "ok", missions: [], roster_changes: [], errors: [] }),
        { status: 200 },
      );
    });

    renderPanel();
    fireEvent.change(screen.getByPlaceholderText("Ask the flight director..."), {
      target: { value: "status report" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Send message" }));

    await waitFor(() => expect(sentMessage).toBe("status report"));
  });

  it("Test 3 (D-08): while sending is true the input and send control are disabled with a loading indicator; both re-enable when settled", async () => {
    const deferred: { resolve: (() => void) | null } = { resolve: null };
    stubFetch(async () => {
      await new Promise<void>((resolve) => {
        deferred.resolve = resolve;
      });
      return new Response(
        JSON.stringify({ message: "ok", missions: [], roster_changes: [], errors: [] }),
        { status: 200 },
      );
    });

    renderPanel();
    fireEvent.change(screen.getByPlaceholderText("Ask the flight director..."), {
      target: { value: "hello" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Send message" }));

    await waitFor(() => {
      expect(screen.getByPlaceholderText("Ask the flight director...")).toBeDisabled();
    });
    expect(screen.getByRole("button", { name: "Send message" })).toBeDisabled();
    expect(screen.getByTestId("chat-loading")).toBeInTheDocument();

    deferred.resolve?.();

    await waitFor(() => {
      expect(screen.getByPlaceholderText("Ask the flight director...")).not.toBeDisabled();
    });
    expect(screen.getByRole("button", { name: "Send message" })).not.toBeDisabled();
    expect(screen.queryByTestId("chat-loading")).not.toBeInTheDocument();
  });

  it("Test 4 (D-05): the collapse toggle hides the transcript and input, leaving a re-expand affordance; toggling again restores them", () => {
    renderPanel();

    expect(screen.getByText("Flight Director standing by")).toBeInTheDocument();
    expect(screen.getByPlaceholderText("Ask the flight director...")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Collapse chat panel" }));

    expect(screen.queryByText("Flight Director standing by")).not.toBeInTheDocument();
    expect(screen.queryByPlaceholderText("Ask the flight director...")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Expand chat panel" })).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Expand chat panel" }));

    expect(screen.getByText("Flight Director standing by")).toBeInTheDocument();
    expect(screen.getByPlaceholderText("Ask the flight director...")).toBeInTheDocument();
  });

  it("Test 5: the panel is rendered as the right-hand column of the page layout, not as an overlay or modal", () => {
    renderPanel();

    const panel = screen.getByTestId("chat-panel");
    expect(panel).not.toHaveAttribute("role", "dialog");
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(panel.className).not.toMatch(/fixed inset-0/);
  });

  it("Test 6 (overflow): adding a turn scrolls the transcript container to its newest message", async () => {
    stubFetch(
      () =>
        new Response(
          JSON.stringify({ message: "Fleet nominal.", missions: [], roster_changes: [], errors: [] }),
          { status: 200 },
        ),
    );

    renderPanel();
    fireEvent.change(screen.getByPlaceholderText("Ask the flight director..."), {
      target: { value: "status" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Send message" }));

    await waitFor(() => {
      expect(screen.getByText("Fleet nominal.")).toBeInTheDocument();
    });
    expect(HTMLElement.prototype.scrollIntoView).toHaveBeenCalled();
  });

  it("Test 7: an assistant turn carrying executed actions renders its confirmation cards inside the transcript", async () => {
    stubFetch(
      () =>
        new Response(
          JSON.stringify({
            message: "Launching now.",
            missions: [
              { drone_id: "FALCON-03", action: "launch", zone: "Riverside", distance_km: 4.2 },
            ],
            roster_changes: [],
            errors: [],
          }),
          { status: 200 },
        ),
    );

    renderPanel();
    fireEvent.change(screen.getByPlaceholderText("Ask the flight director..."), {
      target: { value: "launch falcon 3 to riverside" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Send message" }));

    await waitFor(() => {
      expect(screen.getAllByTestId("confirmation-card")).toHaveLength(1);
    });
    expect(screen.getByText("Dispatched")).toBeInTheDocument();
  });
});
