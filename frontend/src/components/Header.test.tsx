import { render } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { Header } from "./Header";

describe("Header", () => {
  it("Test 6: remainingKwh 0 / energyBudgetKwh 500 renders 0.0 and 500.0, no NaN/minus/undefined", () => {
    const { container } = render(
      <Header
        connectionStatus="connected"
        remainingKwh={0}
        energyBudgetKwh={500}
        activeMissionCount={0}
      />,
    );
    expect(container.textContent).toContain("0.0");
    expect(container.textContent).toContain("500.0");
    expect(container.textContent).not.toContain("NaN");
    expect(container.textContent).not.toContain("-");
    expect(container.textContent).not.toContain("undefined");
  });

  it("Test 7: remainingKwh equal to energyBudgetKwh renders both numerals identically at one decimal", () => {
    const { container } = render(
      <Header
        connectionStatus="connected"
        remainingKwh={500}
        energyBudgetKwh={500}
        activeMissionCount={0}
      />,
    );
    expect(container.textContent).toContain("500.0 / 500.0");
  });

  it("Test 8: remainingKwh 487.3649 renders fixed precision 487.4, not the raw float", () => {
    const { container } = render(
      <Header
        connectionStatus="connected"
        remainingKwh={487.3649}
        energyBudgetKwh={500}
        activeMissionCount={0}
      />,
    );
    expect(container.textContent).toContain("487.4");
    expect(container.textContent).not.toContain("487.3649");
  });

  it("Test 9: null numeric props render the em-dash placeholder, never 0 or NaN", () => {
    const { container } = render(
      <Header
        connectionStatus="connecting"
        remainingKwh={null}
        energyBudgetKwh={null}
        activeMissionCount={null}
      />,
    );
    expect(container.textContent).toContain("—");
    expect(container.textContent).not.toContain("0.0");
    expect(container.textContent).not.toContain("NaN");
  });
});
