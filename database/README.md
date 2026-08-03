# Database

SQLite, single file, lazily initialized. No separate migration tool — see `planning/PLAN.md` section 7 for the full rationale (single operator, zero-config, fresh volumes self-seed).

- `schema.sql` — reference schema definition (source of truth for table shapes)
- `seed_data.md` — what gets seeded on first run and why

## Runtime

At container runtime this directory is the Docker volume mount point (`/app/database`). The backend creates `skyfleet.db` here on first request if it doesn't already exist. The `.db` file itself is gitignored — only this directory's docs and schema are checked in.

## Applying the schema

Once `backend/app/db/` is implemented, it will execute `schema.sql` against a fresh SQLite connection on lazy init. Until then, this file is the contract the backend implementation must satisfy.
