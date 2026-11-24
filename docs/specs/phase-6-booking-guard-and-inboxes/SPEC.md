# Phase 6 — Database-level double-booking guard, booking inboxes, navbar

## Goal

Close the Iron Rule 2 gap with a real PostgreSQL constraint, and give hosts and
guests a place to see and act on bookings.

## 1. PostgreSQL exclusion constraint (Alembic)

The repo gets its Alembic scaffolding (`alembic.ini`, `alembic/env.py`,
`alembic/script.py.mako`, `alembic/versions/`), because AGENTS.md requires
migrations to be Alembic-only. The first migration adds, for PostgreSQL only:

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

**`daterange`, not `tstzrange`.** `check_in` / `check_out` are `DATE` columns.
`EXCLUDE` elements must be immutable, and `date::timestamptz` is only *stable*
(it depends on `TimeZone`), so PostgreSQL rejects it inside the constraint. A
`daterange` matches the data model exactly (a stay is a pair of calendar days),
keeps the half-open `'[)'` convention used by the API, and needs no cast.

On SQLite the migration logs that the constraint is PostgreSQL-only and does
nothing, so `alembic upgrade head` stays runnable in development. The app-level
overlap check stays as the friendly pre-check (`409` with a Persian message).

## 2. Host bookings inbox

- `GET /api/v1/bookings/host` — every booking of a room in a listing the caller
  hosts, newest stay first, enriched with guest name/email, room name, listing
  title. `401` without a token; a host with no listings gets `[]`.
- `PATCH /api/v1/bookings/{id}/confirm` and `.../cancel` — owning host only
  (`404` unknown, `403` someone else's). Both take `Idempotency-Key`.
  Confirm: `pending → confirmed`, already confirmed is a `200` no-op,
  `cancelled → confirmed` is `409`. Cancel: `pending`/`confirmed → cancelled`,
  already cancelled is a `200` no-op. Cancelled bookings release their dates.
- `app/templates/host_bookings.html` at `GET /host/bookings`, linked from the
  host dashboard nav as **رزروهای من**, with تأیید / لغو buttons.

## 3. Guest bookings page

- `GET /api/v1/bookings/mine` — the caller's bookings with room, listing title,
  city and nightly price; `401` without a token.
- `app/templates/profile_bookings.html` at `GET /profile/bookings`, linked from
  the profile page, listing status, dates, nights and total.

## 4. Navbar

`index.html`, `listing_detail.html`, `admin.html` and `profile.html` read
`access_token` from `localStorage`:

- signed in → **پروفایل من** + **خروج** instead of **ورود / ثبتنام**
- **خروج** clears `access_token`, `current_user`, `token_type` and redirects to `/`
- an expired/absent token leaves the login link in place (pages that require
  auth keep redirecting to `/login`)

## Out of scope

Guest-side cancellation, availability calendar, payments, notifications,
splitting the schema into a full Alembic baseline.
