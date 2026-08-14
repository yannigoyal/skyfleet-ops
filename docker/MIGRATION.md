# Migrating from the `skyfleet-data` Docker volume to the host `database/` bind mount

As of this change, `scripts/start_mac.sh`, `scripts/start_windows.ps1`, and
`docker/docker-compose.yml` mount the repository's own `database/` directory
into the container at `/app/database`, instead of the Docker-managed named
volume `skyfleet-data`. This lets the operator open, inspect, and back up
`database/skyfleet.db` directly with ordinary filesystem tools — an opaque
named volume never allowed that.

No script ever deletes the `skyfleet-data` volume. If you ran SkyFleet Ops
before this change, that volume still exists on your machine and still holds
whatever fleet state it had. This document explains what happens to that data
and how to recover it if you want it.

## The accepted default: start fresh

This project accepts the cutover without migrating existing data
(`04-RESEARCH.md` calls this "Option B"). Two reasons:

1. `planning/PLAN.md` §7 designs the database schema for lazy creation and
   default seeding, with no manual migration step anywhere else in the
   system. A bind-mounted container with no `skyfleet.db` present simply
   creates and seeds one on first request, exactly like a fresh Docker
   volume would have.
2. The data sitting in `skyfleet-data` today is exploratory residue from
   manual verification runs, not operational history worth preserving.

If this default is fine for you, do nothing — the next `./scripts/start_mac.sh`
just works, and the old volume is announced (not deleted) so you can still
recover it later if you change your mind.

## Option A: preserve the data in the old volume

If you do want to keep what's in `skyfleet-data`, follow this procedure
before running the updated start script for the first time.

**Why the order matters:** SQLite runs in WAL mode
(`backend/app/db/connection.py`). Committed transactions can live only in the
`-wal` sidecar file until a checkpoint folds them back into the main `.db`
file. Copying `skyfleet.db` alone, without checkpointing first, can silently
drop the most recent writes. Stopping the container before copying prevents
any connection from reopening the WAL mid-copy.

1. **Checkpoint the WAL** so `skyfleet.db` alone is authoritative:

   ```bash
   docker exec skyfleet-ops python3 -c "
   import sqlite3
   conn = sqlite3.connect('/app/database/skyfleet.db')
   conn.execute('PRAGMA wal_checkpoint(TRUNCATE)')
   conn.close()
   "
   ```

2. **Stop the container** so nothing can reopen the WAL while you copy:

   ```bash
   ./scripts/stop_mac.sh
   ```

3. **Copy the file out of the named volume** into the host `database/`
   directory, using a throwaway `alpine` container that mounts both:

   ```bash
   docker run --rm \
     -v skyfleet-data:/from \
     -v "$(pwd)/database:/to" \
     alpine cp /from/skyfleet.db /to/skyfleet.db
   ```

   > **Note:** this repository's `database/` directory may already contain a
   > `skyfleet.db` from local non-Docker runs (`uv run uvicorn ...` outside
   > Docker). If so, the bind-mounted container will adopt that file instead
   > of starting empty. Move it aside first (e.g.
   > `mv database/skyfleet.db database/skyfleet.db.pre-migration`) if you
   > want the copy above to be the one the container reads.

4. **(Optional) Remove the old volume** once you've confirmed the copied
   file is readable and correct:

   ```bash
   docker volume rm skyfleet-data
   ```

   No script in this repository does this automatically — it's a manual,
   deliberate step only you should take once you're satisfied the migration
   worked.

5. **Start normally.** `./scripts/start_mac.sh --build` now bind-mounts
   `database/` and reads the file you copied in step 3.
