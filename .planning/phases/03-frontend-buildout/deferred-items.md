# Deferred Items — Phase 03 (frontend-buildout)

Out-of-scope discoveries logged during plan execution. Not fixed as part of the
originating plan per the SCOPE BOUNDARY rule (only auto-fix issues directly caused
by the current task's changes).

## 03-01

- **`npm run lint` (`next lint`) prompts interactively for ESLint config setup.**
  Found during: Task 2 verification (`cd frontend && npm run lint`, listed in the
  plan's overall `<verification>` block, not in Task 2's own `<verify>` list).
  Cause: ESLint has never been configured for `frontend/` — this predates plan
  03-01 (no `.eslintrc*` file exists, and `frontend/package.json`'s pre-existing
  `lint` script was already `next lint` before this plan touched anything). Not
  caused by this plan's changes (three devDependency additions + two new config
  files + one new test file). Setting up ESLint from scratch is a project-wide
  tooling decision (Rule 4 territory), not a bug introduced here.
  Not fixed. Flagging for whichever future plan owns frontend lint tooling.
