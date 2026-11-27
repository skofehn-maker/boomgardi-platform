# Phase 13 — Production double-booking guard and admin bookings

## Goal

Turn the application-level overlap check into a real database guarantee for
production PostgreSQL, and give admins a full bookings view.

## Current state

- `POST /api/v1/bookings` runs one SQL overlap query inside its transaction
  (`ALEX` guard, ADR 0005) and returns `409`.
- `alembic/versions/0001_booking_no_overlap.py` already creates `btree_gist`
  and `no_overlapping_bookings` (`EXCLUDE USING gist (room_id WITH =,
  daterange(check_in, check_out, '[)') WITH &&) WHERE (status IN ('pending',
  'confirmed'))`) on PostgreSQL; it prints a note and does nothing on SQLite.
- `GET /api/v1/bookings/host` and `/mine` exist; there is no admin-wide view.
- `app/templates/admin.html` has "کاربران" and "اقامتگاه‌ها" views; the
  "رزروها" nav item is a disabled placeholder.

## Requirements

R1. A new migration `0002` (down_revision `0001`) must, on PostgreSQL only:
    - ensure `CREATE EXTENSION IF NOT EXISTS btree_gist`,
    - create `no_overlapping_bookings` **only if absent** (so a database that
      already ran `0001` is not broken by a duplicate constraint),
    - add `ck_bookings_dates` (`check_out > check_in`) if absent.
    On other dialects it must no-op with a log line.
R2. The SQLAlchemy models gain the missing relationships and constraints:
    `Booking.room`/`Booking.guest`, `Room.bookings`, and
    `CheckConstraint("check_out > check_in")`. The exclusion constraint stays
    migration-only: SQLAlchemy's DDL compiler cannot render
    `ExcludeConstraint` on SQLite, which is the development database
    (ADR 0011). The Python overlap check stays for SQLite dev.
R3. `GET /api/v1/bookings/all` — admin only (`get_current_admin`) — returns
    every booking with guest name/email, host name/email, listing, room,
    dates and status. 401 unauthenticated, 403 for non-admins.
R4. `app/templates/admin.html` gets a "مدیریت رزروها" view (enabled in the
    sidebar) with a table of guest, host, listing, dates and status, plus a
    status filter (همه / در انتظار / تأییدشده / لغوشده).

## Out of scope

- Admin mutations on bookings (force-cancel, refunds).
- Server-side filtering/pagination of `/bookings/all`; the requested filter is
  a client-side control and the dataset is small.
- Running the constraint against a real PostgreSQL server (none is available
  here); the migration is verified by offline SQL rendering.
