# ADR 0006 — Alembic baseline and PostgreSQL exclusion constraint

- Status: accepted
- Date: 2026-11-24
- Supersedes the open gap in ADR 0005

## Context

ADR 0005 recorded that Iron Rule 2 (no double booking without a PostgreSQL
`EXCLUDE USING gist`) was not yet satisfied, because the dev database is SQLite
and the project had no Alembic setup even though AGENTS.md declares
"migrations: Alembic only".

## Decision

1. **Alembic scaffolding is now in the repo** (`alembic.ini`, `alembic/env.py`,
   `alembic/versions/`). Its URL comes from `ALEMBIC_DATABASE_URL` when set,
   otherwise from `app.core.config.settings`, so local runs and CI can point it
   at different databases without editing files.

2. **The first migration adds the guard, for PostgreSQL only.**

   ```sql
   CREATE EXTENSION IF NOT EXISTS btree_gist;
   ALTER TABLE bookings
     ADD CONSTRAINT no_overlapping_bookings
     EXCLUDE USING gist (
       room_id WITH =,
       daterange(check_in, check_out, '[)') WITH &&
     )
     WHERE (status IN ('pending', 'confirmed'));
   ```

3. **`daterange` instead of `tstzrange`.** The columns are `DATE`. PostgreSQL
   requires exclusion-constraint expressions to be immutable, and `date` →
   `timestamptz` depends on the session `TimeZone`, so a `tstzrange(...)` form
   would be rejected at creation time. `daterange` is the exact type for a
   calendar-day stay and keeps the half-open `'[)'` semantics the API already
   uses. If the schema ever moves to `timestamptz` columns, the constraint
   becomes `tstzrange(check_in, check_out, '[)')` with no other change.

4. **SQLite skips the migration.** `upgrade()` inspects the bind's dialect and
   returns early with a log line when it is not PostgreSQL, so development and
   tests continue to use the app-level overlap check (`409`). The migration is
   not a no-op in production, where the constraint is the source of truth.

## Consequences

- `alembic upgrade head` is safe to run against `dev.db`; it records the
  revision and prints why it did nothing.
- Production must run `alembic upgrade head` before serving traffic; until it
  does, the app-level check is the only guard.
- The constraint is partial (`pending`/`confirmed`) so a cancelled booking
  immediately frees its dates for re-booking, which the API tests assert.
- The table schema itself is still created by `create_db.py`; the Alembic
  baseline for existing tables is deliberately out of scope here.
