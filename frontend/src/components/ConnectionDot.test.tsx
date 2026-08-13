import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ConnectionDot } from "@/components/ConnectionDot";
import type { ConnectionStatus } from "@/lib/useTelemetryStream";

const CASES: Array<{ status: ConnectionStatus; label: string }> = [
  { status: "connected", label: "Live" },
  { status: "connecting", label: "Connecting" },
  { status: "disconnected", label: "Disconnected" },
];

describe("ConnectionDot", () => {
  it.each(CASES)("renders the $label label for status $status", ({ status, label }) => {
    render(<ConnectionDot status={status} />);
    expect(screen.getByText(label)).toBeInTheDocument();
  });
});
