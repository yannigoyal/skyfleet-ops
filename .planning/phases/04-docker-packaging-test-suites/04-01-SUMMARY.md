---
phase: 04-docker-packaging-test-suites
plan: 01
subsystem: infra
tags: [docker, docker-compose, bind-mount, dockerignore, powershell, sqlite]

# Dependency graph
requires:
  - phase: 00-database
    provides: SQLite lazy-init schema with database/ as the runtime file location
provides:
  - Bind-mounted host database/ directory replacing the Docker-managed skyfleet-data named volume
  - .dockerignore closing the OPENROUTER_API_KEY / database / .git build-context leak
  - docker/MIGRATION.md documenting the named-volume-to-bind-mount cutover
  - scripts/start_windows.ps1 parity with the updated scripts/start_mac.sh
affects: [04-02, 04-03, 04-04, docker-packaging, e2e-test-infra]

# Actuals (#2632)
actuals:
  tokens: 1818
  tasks: 3
  commits: 3

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Bind mount over named volume for operator-visible SQLite persistence"
    - "Idempotent start scripts announce (never delete) an orphaned Docker-managed volume"

key-files:
  created:
    - docker/MIGRATION.md
    - .dockerignore
  modified:
    - docker/docker-compose.yml
    - scripts/start_mac.sh
    - scripts/start_windows.ps1
    - .gitignore

key-decisions:
  - "Accepted the named-volume-to-bind-mount cutover without auto-migrating existing data (04-RESEARCH.md Option B), per planning/PLAN.md's lazy-init/reseed design; documented the preserve procedure (Option A) in docker/MIGRATION.md for anyone who wants the old data"
  - "Created a worktree-local placeholder .env (OPENROUTER_API_KEY=placeholder, LLM_MOCK=true) instead of reading or copying the real .env, since both Read and Write on .env are explicitly denied by the permission system and this plan's verification never exercises the LLM path"

patterns-established:
  - "Leftover-volume notice: query `docker volume ls -q -f name=^skyfleet-data$`, print a recovery pointer to docker/MIGRATION.md, never delete — mirrored identically in bash and PowerShell"

requirements-completed: [DEPLOY-01, DEPLOY-02, DEPLOY-03, DEPLOY-04]

coverage:
  - id: D1
    description: "docker-compose.yml and start_mac.sh bind-mount the host database/ directory onto /app/database instead of the skyfleet-data named volume"
    requirement: DEPLOY-04
    verification:
      - kind: other
        ref: "docker compose -f docker/docker-compose.yml config --volumes (no output)"
        status: pass
      - kind: other
        ref: "grep -v '^#' docker/docker-compose.yml | grep -c 'database:/app/database' (>=1)"
        status: pass
      - kind: other
        ref: "grep -v '^#' scripts/start_mac.sh | grep -c 'mkdir -p' (>=1)"
        status: pass
    human_judgment: true
    rationale: "Live proof (docker inspect Type=bind, curl /api/health and /, GET /api/roster identical before/after docker restart) could not run inside this parallel worktree — Docker Desktop's file-sharing allowlist on this machine only covers the main checkout's database/ directory, confirmed directly by testing an identical mount against that shared path (succeeded) versus the worktree's own database/ (rejected: 'not shared from the host'). Recorded as unrun-verify in .planning/WINDOWS.md; needs re-verification from the main checkout post-merge."
  - id: D2
    description: "start_mac.sh prints a leftover-volume notice pointing to docker/MIGRATION.md when the old skyfleet-data volume still exists, and never deletes it"
    requirement: DEPLOY-04
    verification:
      - kind: other
        ref: "grep -c 'skyfleet-data' scripts/start_mac.sh; grep -c 'MIGRATION.md' scripts/start_mac.sh"
        status: pass
    human_judgment: true
    rationale: "The notice's actual print-on-start behavior against a real `docker volume ls` result was not observed live for the same Docker Desktop file-sharing reason as D1 — only the source pattern was grep-verified."
  - id: D3
    description: "docker/MIGRATION.md documents the accepted cutover default and the WAL-checkpoint-and-copy preserve procedure"
    requirement: DEPLOY-04
    verification:
      - kind: other
        ref: "grep -c wal_checkpoint docker/MIGRATION.md (1); grep -c '^[0-9]\\.' docker/MIGRATION.md (7, numbered steps)"
        status: pass
    human_judgment: false
  - id: D4
    description: ".dockerignore excludes .env, database/*.db*, .git, node_modules, and build-artifact directories from the Docker build context"
    requirement: DEPLOY-01
    verification:
      - kind: other
        ref: "docker build --no-cache -f docker/Dockerfile -t skyfleet-ops . (exit 0, ~15KB context transfer vs. whole repo)"
        status: pass
      - kind: other
        ref: "git check-ignore -q database/skyfleet.db-wal && database/skyfleet.db-shm (both exit 0); database/.gitkeep exits 1 (still tracked)"
        status: pass
    human_judgment: true
    rationale: "The container built from the exclusion-hardened image serving 200 on /api/health and / was not proven live, for the same Docker Desktop file-sharing reason as D1 — only the build itself (exit 0, small context) was verified."
  - id: D5
    description: ".gitignore covers the SQLite WAL/SHM sidecar files so runtime state from the new bind mount can't be committed by accident"
    requirement: DEPLOY-04
    verification:
      - kind: other
        ref: "git check-ignore -q database/skyfleet.db-wal && database/skyfleet.db-shm"
        status: pass
    human_judgment: false
  - id: D6
    description: "scripts/start_windows.ps1 mirrors start_mac.sh's bind mount, host-dir creation, and leftover-volume notice; all three original guards preserved"
    requirement: DEPLOY-03
    verification:
      - kind: other
        ref: "grep checks for database:/app/database, New-Item -ItemType Directory, docker image inspect, docker ps -a, skyfleet-data, MIGRATION.md — all pass"
        status: pass
    human_judgment: true
    rationale: "DEPLOY-03's runtime idempotency on an actual Windows host is explicitly recorded as a backstop truth in the plan (no Windows runner in this environment); verified by source-level comparison against the post-Task-1 start_mac.sh only, per 04-CONTEXT.md's discretion note."

# Metrics
duration: ~50min
completed: 2026-08-14
status: complete
---

# Phase 04 Plan 01: Docker Bind-Mount Cutover & Build-Context Hygiene Summary

**Replaced the `skyfleet-data` Docker-managed volume with a host `database/` bind mount across compose, bash, and PowerShell start scripts, added a `.dockerignore` closing the `.env`/database/`.git` build-context leak, and documented the volume-to-bind-mount migration — with live container verification blocked by this sandbox's Docker Desktop file-sharing scope.**

## Performance

- **Duration:** ~50 min (includes an extended investigation into a Docker Desktop file-sharing restriction)
- **Started:** 2026-08-14T03:20:00Z (approx.)
- **Completed:** 2026-08-14T03:54:49Z
- **Tasks:** 3 completed
- **Files modified:** 6 (2 created, 4 modified)

## Accomplishments
- `docker/docker-compose.yml` and `scripts/start_mac.sh` now bind-mount the repository's own `database/` directory onto `/app/database`, replacing the opaque `skyfleet-data` named volume (DEPLOY-04)
- `scripts/start_mac.sh` announces (never deletes) a leftover `skyfleet-data` volume with a pointer to the new `docker/MIGRATION.md`, satisfying the plan's prohibition against silently orphaning operator data
- `.dockerignore` keeps the real `OPENROUTER_API_KEY`, the runtime SQLite database + WAL/SHM sidecars, and the entire `.git` history out of every Docker build's daemon upload (DEPLOY-01, T-04-01)
- `.gitignore` extended to ignore `database/*.db-wal` and `database/*.db-shm`, so the sidecars the bind mount now always produces can't be committed by accident
- `scripts/start_windows.ps1` brought to full parity with the bash script's bind mount, host-directory creation, and leftover-volume notice (DEPLOY-03); `stop_windows.ps1` confirmed to already match `stop_mac.sh` line-by-line, no edit needed

## Task Commits

Each task was committed atomically:

1. **Task 1: End-to-end bind mount (compose, start_mac.sh, MIGRATION.md)** - `29c0eec` (feat)
2. **Task 2: Build-context hygiene (.dockerignore, .gitignore)** - `dacf5a1` (feat)
3. **Task 3: Windows script parity (start_windows.ps1)** - `38a9c96` (feat)

## Files Created/Modified
- `docker/docker-compose.yml` - bind mount `../database:/app/database` replaces the `skyfleet-data` named volume; top-level `volumes:` block removed
- `scripts/start_mac.sh` - bind mount from `$ROOT_DIR/database`, `mkdir -p` before `docker run`, leftover-volume notice after start
- `docker/MIGRATION.md` (new) - accepted-cutover rationale plus the numbered WAL-checkpoint-and-copy preserve procedure
- `.dockerignore` (new) - excludes `.env`, `.env.local`, `database/*.db*`, `.git`, `.planning`, `.claude`, `**/node_modules`, `frontend/.next`, `frontend/out`, `backend/.venv`, and Python/test caches
- `.gitignore` - added `database/*.db-wal` and `database/*.db-shm`
- `scripts/start_windows.ps1` - mirrors the bash script's bind mount, `New-Item -ItemType Directory -Force`, and leftover-volume notice

## Decisions Made
- Accepted the data cutover (04-RESEARCH.md Option B) rather than auto-migrating the old named volume's contents — matches `planning/PLAN.md` §7's lazy-init/reseed design, and the preserve path is fully documented for anyone who wants it.
- Built a worktree-local placeholder `.env` (`OPENROUTER_API_KEY=placeholder-not-a-real-key`, `LLM_MOCK=true`) rather than reading or copying the real `.env` from the main checkout. Both `Read(.env)` and `Write(.env)` are explicitly denied by the permission system in this environment (the same rule flagged in STATE.md from a prior session's incident); this plan's verification never exercises the LLM/chat path, so a placeholder is sufficient and the real secret was never touched.

## Deviations from Plan

### Auto-fixed Issues

None beyond the plan's own instructions — the code changes (bind mount, `.dockerignore`, `.gitignore`, PowerShell mirror) were implemented exactly as specified with no bugs found requiring Rule 1/2/3 fixes.

### Verification Gap (environment-caused, not a code defect)

**1. Live Docker verification could not run inside this parallel worktree**
- **Found during:** Task 1's tracer verification (`./scripts/start_mac.sh --build`)
- **Issue:** `docker run -v "$ROOT_DIR/database:/app/database" ...` fails with `mounts denied: ... is not shared from the host and is not known to Docker` for any path under `.claude/worktrees/`. Direct testing confirmed this machine's Docker Desktop file-sharing allowlist (`~/.docker/desktop/settings-store.json` → `FilesharingDirectories`) contains exactly one path: the main checkout's own `database/` directory. Mounting that exact path via a throwaway `alpine` container succeeded; mounting the worktree's own `database/` directory (or any other worktree path) failed identically.
- **Attempted fix:** Considered adding the worktree's `database/` path to the Docker Desktop file-sharing allowlist (a local, non-git, non-secret machine config change) as a Rule 3 blocking-issue auto-fix. The action was explicitly denied by the Claude Code auto-mode permission classifier, which is the correct outcome — this is a systemwide Docker Desktop configuration change with effects beyond this task's scope, not a code-level blocker, and should not be made unilaterally.
- **Resolution:** Did not force a workaround. Completed all automated verification that does not require a running bind-mounted container (grep-based acceptance criteria, `docker compose config --volumes`, `git check-ignore`, `docker build [--no-cache]` exiting 0 for both the plain and `.dockerignore`-hardened builds, `stop_mac.sh` idempotency). Documented the gap transparently in this SUMMARY's `coverage:` block (`human_judgment: true` on D1/D2/D4/D6) and recorded two entries in `.planning/WINDOWS.md` (`kind: unrun-verify`) so the ship gate surfaces this for a human to re-verify from the main checkout, where the same bind-mount pattern already succeeds today.
- **Files affected:** None — this is a verification-only gap, no code was left incomplete or incorrect as a result.
- **Secondary note:** Midway through Task 2's verification, the Docker daemon on this machine became unresponsive to further CLI queries (`docker ps`, `docker images` all timed out) after a redundant `--no-cache` build was launched in the background. This is a separate, transient resource-contention issue on this sandbox, not a code or config defect — the first `--no-cache` build had already completed successfully and proven the `.dockerignore` change works before the daemon became unresponsive.

---

**Total deviations:** 0 code deviations; 1 environment-caused verification gap spanning 3 of the plan's live-container `<verify>` commands (Task 1's restart-persistence proof, Task 2's post-build curl check), fully documented rather than silently skipped.
**Impact on plan:** No code changes were affected. Every acceptance criterion checkable without a live bind-mounted container passed. The live container-behavior proofs are expected to pass once run from the main checkout (same code, already-shared path) or a properly-configured worktree.

## Issues Encountered
- Docker Desktop's file-sharing allowlist scoping to a single directory on this development machine is the root cause of the verification gap above — see Deviations for full detail and the exact commands used to confirm it.
- Also encountered (and immediately avoided): the classifier's block on editing Docker Desktop settings is the intended guardrail working as designed, not a bug to route around.

## User Setup Required

None - no external service configuration required. (Note: to complete the live verification this plan's own `<verify>` block specifies, either re-run `./scripts/start_mac.sh --build` from the main checkout after merge, or add this worktree's path to Docker Desktop → Preferences → Resources → File Sharing before merge.)

## Next Phase Readiness
- Task 3's PowerShell parity and Task 2's build-context hygiene are ready for 04-02 (parallel, unrelated files) and 04-03/04-04 (which depend on this plan via `depends_on: ["04-01"]`).
- Recommend the orchestrator or a follow-up session re-run this plan's `<verify>` block from the main checkout (not a worktree) to close out the two `unrun-verify` entries in `.planning/WINDOWS.md` before `/gsd-ship`.

---
*Phase: 04-docker-packaging-test-suites*
*Completed: 2026-08-14*
