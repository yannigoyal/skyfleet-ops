import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { DispatchBar } from "./DispatchBar";

function mockFetch(response: Partial<Response> = {}) {
  const fetchMock = vi.fn().mockResolvedValue({
    ok: true,
    status: 201,
    statusText: "Created",
    json: async () => ({}),
    ...response,
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

describe("DispatchBar", () => {
  beforeEach(() => vi.unstubAllGlobals());

  it("posts a launch to /api/fleet/missions and refreshes", async () => {
    const fetchMock = mockFetch();
    const onDispatched = vi.fn();
    render(<DispatchBar onDispatched={onDispatched} />);

    await userEvent.type(screen.getByLabelText("Drone"), "FALCON-03");
    await userEvent.type(screen.getByLabelText("Zone"), "Riverside");
    await userEvent.type(screen.getByLabelText("Distance km"), "4.2");
    await userEvent.click(screen.getByRole("button", { name: "Launch" }));

    await waitFor(() => expect(onDispatched).toHaveBeenCalled());
    const [path, init] = fetchMock.mock.calls[0];
    expect(path).toBe("/api/fleet/missions");
    expect(init.method).toBe("POST");
    expect(JSON.parse(init.body)).toEqual({
      drone_id: "FALCON-03",
      zone: "Riverside",
      distance_km: 4.2,
    });
  });

  it("deletes the mission for the drone on recall", async () => {
    const fetchMock = mockFetch({ status: 200 });
    render(<DispatchBar onDispatched={vi.fn()} />);

    await userEvent.type(screen.getByLabelText("Drone"), "FALCON-03");
    await userEvent.click(screen.getByRole("button", { name: "Recall" }));

    await waitFor(() => expect(fetchMock).toHaveBeenCalled());
    const [path, init] = fetchMock.mock.calls[0];
    expect(path).toBe("/api/fleet/missions/FALCON-03");
    expect(init.method).toBe("DELETE");
  });

  it("shows the backend error reason when a launch fails", async () => {
    mockFetch({
      ok: false,
      status: 422,
      json: async () => ({ detail: { reason: "insufficient_budget" } }),
    });
    render(<DispatchBar onDispatched={vi.fn()} />);

    await userEvent.type(screen.getByLabelText("Drone"), "FALCON-03");
    await userEvent.type(screen.getByLabelText("Zone"), "Riverside");
    await userEvent.type(screen.getByLabelText("Distance km"), "9");
    await userEvent.click(screen.getByRole("button", { name: "Launch" }));

    expect(await screen.findByText("insufficient_budget")).toBeInTheDocument();
  });
});
