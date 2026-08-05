# Review Findings

## Findings

- P2 - `docs/SETUP.md:85` and `docs/SETUP.md:111` document automatic SQLite creation/seeding and recovery by deleting `database/skyfleet.db`, but the current backend does not initialize or touch SQLite at all. `backend/app/main.py:22-45` only starts telemetry and mounts static files, and `frontend/src/app/page.tsx:8-10` explicitly says mission control, chat, and roster CRUD are not built yet. A new user following the setup guide will look for a database file and seeded state that never appears. Reword this section to match the implemented telemetry-only state, or add the database initialization path before publishing the guide.

- P2 - `docs/SETUP.md:8`, `docs/SETUP.md:32`, `docs/SETUP.md:92`, and `docs/SETUP.md:99` present the OpenRouter-backed AI flight director chat as an available feature and make `OPENROUTER_API_KEY` required, but the UI only renders a placeholder stating chat is not implemented (`frontend/src/app/page.tsx:26-28`) and there is no `/api/chat` route in `backend/app/main.py:33-39`. This makes the documented prerequisites and expected first-run experience misleading. Mark the key/chat as planned or optional until the backend and UI exist.

- P2 - `planning/PLAN.md:398` changes the documented persistence strategy to a project-directory bind mount, but the actual Docker entry points still use the named Docker volume `skyfleet-data`. The checked-in `docker/docker-compose.yml:13`, `scripts/start_mac.sh:35`, `scripts/start_windows.ps1:35`, and `README.md:37` all mount `skyfleet-data:/app/database`, while nearby plan text still says fresh Docker volumes are used at `planning/PLAN.md:192`. This leaves the plan internally inconsistent and gives operators two different persistence models depending on which document they read. Either update the scripts/compose/README to use the bind mount or keep the plan on the named volume.

- P3 - `planning/PLAN.md:172` introduces a typo: "multi-ofleet". This is minor, but it is in the primary architecture plan and should be corrected before committing the documentation change.

- P3 - `.claude/settings.local.json:1` is an untracked local Claude settings file, and `.gitignore:40-47` does not exclude `.claude/settings.local.json`. If `.claude/` is added as-is, a machine-specific permission allowlist for `Bash(git add *)` becomes part of the shared repo. Local tool permissions are usually workstation state, so either ignore this file or replace it with an intentionally shared project settings file.

## Open Questions

- Is the intended database persistence model still the named Docker volume, or should the project switch all Docker entry points to a bind mount?

## Summary

Reviewed the tracked `planning/PLAN.md` changes and the untracked `.claude/` and `docs/` additions since `HEAD`. No runtime code changed, so no tests were run.
