import { test, expect } from "@playwright/test";

// The one endpoint that already exists end-to-end today. Everything else in
// this directory is written against APIs specified in planning/PLAN.md but
// not yet implemented — see tests/README.md for the full scenario list.
test("backend health check responds ok", async ({ request }) => {
  const response = await request.get("/api/health");
  expect(response.ok()).toBeTruthy();
  expect(await response.json()).toEqual({ status: "ok" });
});
