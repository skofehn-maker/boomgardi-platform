# Phase 13 — PLAN

## Steps

1. Failing tests (`tests/test_admin_bookings.py`):
   - `GET /api/v1/bookings/all` → 401 without a token, 403 as guest and as host.
   - As admin → 200 with one row per booking, carrying `guest_name`,
     `guest_email`, `host_name`, `listing_title`, `room_name`, dates and status,
     including a cancelled booking.
   - `GET /admin` contains "مدیریت رزروها", `/api/v1/bookings/all`,
     `booking-status-filter` and the three Persian status labels.
   - `Booking.room` / `Booking.guest` / `Room.bookings` exist; `bookings` has a
     `ck_bookings_dates` check constraint.
   - The newest migration in `alembic/versions/` contains `btree_gist`,
     `EXCLUDE USING gist`, its `down_revision` is the previous revision, and it
     guards creation with `IF NOT EXISTS`.
2. `app/schemas/booking.py`: `AdminBookingResponse`.
3. `app/api/v1/bookings.py`: `GET /all` with `get_current_admin`, joining guest
   and host `User` aliases.
4. `app/models/booking.py`: relationships + check constraint;
   `app/models/listing.py`: `Room.bookings` back-reference.
5. `alembic/versions/0002_booking_guard_and_relationships.py`.
6. `app/templates/admin.html`: sidebar link, `view-bookings` section, CSS-less
   reuse of existing table/badge classes, and the load/render/filter JS.
7. `docs/adr/0011-exclusion-constraint-stays-in-the-migration.md`.
8. Full `pytest`, offline `alembic upgrade --sql` for PostgreSQL to prove the
   migration renders, then commit and push.

## Iron rules

- Rule 1: this SPEC/PLAN and the failing tests precede the code.
- Rule 2: the guarantee is the PostgreSQL exclusion constraint; the Python
  check remains only as the SQLite-dev/UX guard.
- Rule 3: unchanged — `check_in`/`check_out` are calendar dates, `created_at`
  stays UTC.
- Rule 4: no new mutating endpoint.
- Rule 6: ADR 0011.
- Rule 7: full suite before the commit.

## Verification limit

No PostgreSQL server is reachable from this machine, so the constraint is
proven to *render* (offline SQL), not to *reject* a concurrent insert. That gap
is reported in the final message.
