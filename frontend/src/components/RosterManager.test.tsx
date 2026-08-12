import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { RosterManager } from "./RosterManager";

function mockFetch() {
  const fetchMock = vi
    .fn()
    .mockResolvedValue({ ok: true, status: 200, statusText: "OK", json: async () => ({}) });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

describe("RosterManager", () => {
  beforeEach(() => vi.unstubAllGlobals());

  it("posts a new drone to /api/roster and clears the input", async () => {
    const fetchMock = mockFetch();
    const onChanged = vi.fn();
    render(<RosterManager roster={[]} onChanged={onChanged} />);

    const input = screen.getByLabelText("New drone ID");
    await userEvent.type(input, "FALCON-11");
    await userEvent.click(screen.getByRole("button", { name: "Add" }));

    await waitFor(() => expect(onChanged).toHaveBeenCalled());
    const [path, init] = fetchMock.mock.calls[0];
    expect(path).toBe("/api/roster");
    expect(init.method).toBe("POST");
    expect(JSON.parse(init.body)).toEqual({ drone_id: "FALCON-11" });
    expect(input).toHaveValue("");
  });

  it("deletes a drone from /api/roster/{drone_id}", async () => {
    const fetchMock = mockFetch();
    render(<RosterManager roster={[{ drone_id: "FALCON-02" }]} onChanged={vi.fn()} />);

    await userEvent.click(screen.getByRole("button", { name: "Remove FALCON-02" }));

    await waitFor(() => expect(fetchMock).toHaveBeenCalled());
    const [path, init] = fetchMock.mock.calls[0];
    expect(path).toBe("/api/roster/FALCON-02");
    expect(init.method).toBe("DELETE");
  });

  it("lists the current roster", () => {
    render(
      <RosterManager
        roster={[{ drone_id: "FALCON-01" }, { drone_id: "FALCON-02" }]}
        onChanged={vi.fn()}
      />,
    );
    expect(screen.getByText("FALCON-01")).toBeInTheDocument();
    expect(screen.getByText("FALCON-02")).toBeInTheDocument();
  });
});
