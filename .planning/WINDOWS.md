---
schema_version: 1
open_count: 5
waived_count: 0
fixed_count: 0
total_count: 5
last_updated: 2026-08-14T06:43:00.011Z
---

# Broken Windows Ledger

> Cross-phase defect register. With `workflow.windows_enforce` enabled, `/gsd-ship` blocks while `open_count > 0`.
> Waive with `gsd-tools windows waive <id> "<reason>"` (reason required).
> Mark fixed with `gsd-tools windows fixed <id>`.

| id | phase | kind | file | line | description | status | reason | recorded_at | resolved_at |
|----|-------|------|------|------|-------------|--------|--------|-------------|-------------|
| 1 | 04 | unrun-verify | docker/docker-compose.yml |  | Live bind-mount + restart-persistence verification (docker inspect Type=bind, curl /api/health and /, GET /api/roster before/after docker restart) could not run inside this parallel worktree: Docker Desktop file-sharing on this machine only shares the main checkout's database/ dir, not paths under .claude/worktrees/. Re-verify from the main checkout post-merge. | open |  | 2026-08-14T03:53:26.099Z |  |
| 2 | 04 | unrun-verify | .dockerignore |  | Task 2's chained verify (docker build --no-cache && ./scripts/start_mac.sh && curl /api/health) could not complete live inside this parallel worktree, for the same Docker Desktop file-sharing reason as the docker/docker-compose.yml entry. The --no-cache build itself was verified to exit 0 with a small (~15KB) build context; only the subsequent container run + curl was blocked. | open |  | 2026-08-14T03:53:30.834Z |  |
| 3 | 04 | unrun-verify | tests/specs/visualization.spec.ts |  | Live docker-compose E2E run (docker compose up --build) not attempted this session — host disk at 98% capacity, 3.1GB free, matching 04-01/04-03's documented ENOSPC risk in this sandbox | open |  | 2026-08-14T06:42:57.619Z |  |
| 4 | 04 | unrun-verify | tests/specs/chat.spec.ts |  | Live docker-compose E2E run not attempted this session — same host disk pressure gap as visualization.spec.ts | open |  | 2026-08-14T06:42:58.664Z |  |
| 5 | 04 | unrun-verify | tests/specs/sse-resilience.spec.ts |  | Live docker-compose E2E run not attempted this session — same host disk pressure gap; the route-abort-then-reload mechanism's live reconnect behavior (this plan's flagged prohibition T-04-16) is unverified in practice | open |  | 2026-08-14T06:43:00.011Z |  |

````json
[
  {
    "id": 1,
    "kind": "unrun-verify",
    "phase": "04",
    "file": "docker/docker-compose.yml",
    "line": null,
    "description": "Live bind-mount + restart-persistence verification (docker inspect Type=bind, curl /api/health and /, GET /api/roster before/after docker restart) could not run inside this parallel worktree: Docker Desktop file-sharing on this machine only shares the main checkout's database/ dir, not paths under .claude/worktrees/. Re-verify from the main checkout post-merge.",
    "status": "open",
    "reason": "",
    "recorded_at": "2026-08-14T03:53:26.099Z",
    "resolved_at": null
  },
  {
    "id": 2,
    "kind": "unrun-verify",
    "phase": "04",
    "file": ".dockerignore",
    "line": null,
    "description": "Task 2's chained verify (docker build --no-cache && ./scripts/start_mac.sh && curl /api/health) could not complete live inside this parallel worktree, for the same Docker Desktop file-sharing reason as the docker/docker-compose.yml entry. The --no-cache build itself was verified to exit 0 with a small (~15KB) build context; only the subsequent container run + curl was blocked.",
    "status": "open",
    "reason": "",
    "recorded_at": "2026-08-14T03:53:30.834Z",
    "resolved_at": null
  },
  {
    "id": 3,
    "kind": "unrun-verify",
    "phase": "04",
    "file": "tests/specs/visualization.spec.ts",
    "line": null,
    "description": "Live docker-compose E2E run (docker compose up --build) not attempted this session — host disk at 98% capacity, 3.1GB free, matching 04-01/04-03's documented ENOSPC risk in this sandbox",
    "status": "open",
    "reason": "",
    "recorded_at": "2026-08-14T06:42:57.619Z",
    "resolved_at": null
  },
  {
    "id": 4,
    "kind": "unrun-verify",
    "phase": "04",
    "file": "tests/specs/chat.spec.ts",
    "line": null,
    "description": "Live docker-compose E2E run not attempted this session — same host disk pressure gap as visualization.spec.ts",
    "status": "open",
    "reason": "",
    "recorded_at": "2026-08-14T06:42:58.664Z",
    "resolved_at": null
  },
  {
    "id": 5,
    "kind": "unrun-verify",
    "phase": "04",
    "file": "tests/specs/sse-resilience.spec.ts",
    "line": null,
    "description": "Live docker-compose E2E run not attempted this session — same host disk pressure gap; the route-abort-then-reload mechanism's live reconnect behavior (this plan's flagged prohibition T-04-16) is unverified in practice",
    "status": "open",
    "reason": "",
    "recorded_at": "2026-08-14T06:43:00.011Z",
    "resolved_at": null
  }
]
````
