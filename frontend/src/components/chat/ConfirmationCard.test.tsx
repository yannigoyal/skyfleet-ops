import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { ConfirmationCard } from "./ConfirmationCard";
import { ChatMessage } from "./ChatMessage";

describe("ConfirmationCard — one compact, equally-weighted card per executed action or error", () => {
  it("Test 1: a launch action renders the verb, drone id, zone, distance with km suffix, and an emerald Dispatched badge", () => {
    render(
      <ConfirmationCard
        kind="success"
        entry={{ drone_id: "FALCON-03", action: "launch", zone: "Riverside", distance_km: 4.2 }}
      />,
    );

    const card = screen.getByTestId("confirmation-card");
    expect(card.textContent).toContain("LAUNCH");
    expect(card.textContent).toContain("FALCON-03");
    expect(card.textContent).toContain("Riverside");
    expect(card.textContent).toContain("4.2km");
    expect(screen.getByText("Dispatched")).toHaveClass("text-emerald-400");
  });

  it("Test 2: a recall action renders the verb, drone id, and Recalled badge, with no zone/distance and no undefined or NaN", () => {
    render(
      <ConfirmationCard kind="success" entry={{ drone_id: "FALCON-07", action: "recall" }} />,
    );

    const card = screen.getByTestId("confirmation-card");
    expect(card.textContent).toContain("RECALL");
    expect(card.textContent).toContain("FALCON-07");
    expect(card.textContent).not.toMatch(/undefined|NaN/);
    expect(screen.getByText("Recalled")).toHaveClass("text-emerald-400");
  });

  it("Test 3: roster add and remove actions render emerald Added and Removed badges respectively", () => {
    const { unmount } = render(
      <ConfirmationCard kind="success" entry={{ drone_id: "FALCON-11", action: "add" }} />,
    );
    expect(screen.getByText("Added")).toHaveClass("text-emerald-400");
    unmount();

    render(<ConfirmationCard kind="success" entry={{ drone_id: "FALCON-11", action: "remove" }} />);
    expect(screen.getByText("Removed")).toHaveClass("text-emerald-400");
  });

  it("Test 4 (prohibition): an error string renders its own card with a red Failed: badge and the error text, never a success badge", () => {
    render(
      <ConfirmationCard kind="failure" message="Could not recall FALCON-09: no_active_mission." />,
    );

    const card = screen.getByTestId("confirmation-card");
    expect(card.textContent).toContain("Failed:");
    expect(card.textContent).toContain("Could not recall FALCON-09: no_active_mission.");
    expect(screen.queryByText("Dispatched")).not.toBeInTheDocument();
    expect(screen.queryByText("Recalled")).not.toBeInTheDocument();
    expect(screen.queryByText("Added")).not.toBeInTheDocument();
    expect(screen.queryByText("Removed")).not.toBeInTheDocument();
  });

  it("Test 5 (prohibition): one executed mission plus one error renders exactly two cards, neither omitted", () => {
    render(
      <>
        <ConfirmationCard
          kind="success"
          entry={{ drone_id: "FALCON-03", action: "launch", zone: "Riverside", distance_km: 4.2 }}
        />
        <ConfirmationCard kind="failure" message="Could not recall FALCON-09: no_active_mission." />
      </>,
    );

    const cards = screen.getAllByTestId("confirmation-card");
    expect(cards).toHaveLength(2);
    expect(screen.getByText("Dispatched")).toBeInTheDocument();
    expect(screen.getByText("Failed:")).toBeInTheDocument();
  });

  it("Test 6 (encoding): an HTML-looking, multi-byte zone renders as literal visible text with no element created and no character split", () => {
    const dangerousZone = '<img src=x onerror=alert(1)>日本語テスト';
    render(
      <ConfirmationCard
        kind="success"
        entry={{ drone_id: "FALCON-05", action: "launch", zone: dangerousZone, distance_km: 1 }}
      />,
    );

    const card = screen.getByTestId("confirmation-card");
    expect(card.textContent).toContain(dangerousZone);
    expect(card.querySelectorAll("img").length).toBe(0);
  });

  it("Test 7: a very long zone name truncates with an ellipsis and carries a native title attribute holding the full value", () => {
    const longZone = "A".repeat(80) + " Very Long Delivery Zone Name Indeed";
    render(
      <ConfirmationCard
        kind="success"
        entry={{ drone_id: "FALCON-05", action: "launch", zone: longZone, distance_km: 1 }}
      />,
    );

    const zoneEl = screen.getByTitle(longZone);
    expect(zoneEl).toBeInTheDocument();
    expect(zoneEl.className).toContain("truncate");
  });

  it("Test 8: an assistant turn with no actions and no errors renders its message text and no cards at all", () => {
    render(
      <ChatMessage
        turn={{ role: "assistant", content: "Fleet is healthy, all drones nominal." }}
      />,
    );

    expect(screen.getByText("Fleet is healthy, all drones nominal.")).toBeInTheDocument();
    expect(screen.queryAllByTestId("confirmation-card")).toHaveLength(0);
  });
});
