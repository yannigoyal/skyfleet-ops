# Deferred Items — Phase 04 (docker-packaging-test-suites)

Out-of-scope discoveries logged during plan execution. Not fixed as part of the
originating plan per the SCOPE BOUNDARY rule (only auto-fix issues directly caused
by the current task's changes).

## 04-02

- **`npm run lint` (`next lint`) prompts interactively for ESLint config setup,
  exits 1 under non-interactive stdin.**
  Found during: Task 2 verification (`cd frontend && npm run lint`, listed in
  Task 2's `<verify>` block and the plan's overall `<verification>` block).
  Cause: ESLint has never been configured for `frontend/` — no `.eslintrc*` or
  `eslint.config.*` file exists, and `eslint` is not a declared dependency in
  `frontend/package.json`. This predates this plan; it was first found and
  deferred during 03-01 (see `.planning/phases/03-frontend-buildout/deferred-items.md`)
  and remains unresolved. Not caused by 04-02's changes (this plan made zero
  frontend source changes — the audit found no coverage gap).
  Not fixed. `npx tsc --noEmit` (the other half of that acceptance criterion)
  exits 0 cleanly. Flagging again for whichever future plan owns frontend lint
  tooling — setting up ESLint from scratch is a project-wide tooling decision
  (Rule 4 territory), not a bug introduced here or in 03-01.
