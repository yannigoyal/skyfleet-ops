import "@testing-library/jest-dom/vitest";

// jsdom has no ResizeObserver implementation; Recharts' ResponsiveContainer
// requires one even when given fixed numeric width/height props (it still
// wires up an observer to react to future container resizes).
class ResizeObserverStub {
  observe() {}
  unobserve() {}
  disconnect() {}
}
if (typeof globalThis.ResizeObserver === "undefined") {
  globalThis.ResizeObserver = ResizeObserverStub as unknown as typeof ResizeObserver;
}

// jsdom has no scrollIntoView implementation; ChatPanel calls it on every
// new transcript turn to auto-scroll to the newest message (FE-08).
if (typeof HTMLElement.prototype.scrollIntoView === "undefined") {
  HTMLElement.prototype.scrollIntoView = function scrollIntoViewStub() {};
}
