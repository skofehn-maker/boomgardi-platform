# Phase 5 — Rooms and bookings

## Goal

A host can give a listing bookable rooms, and a guest can open a listing, pick
dates and book a room — with overlapping stays refused.

## 1. Rooms (backend + host UI)

`POST /api/v1/listings/{listing_id}/rooms`

- Body: `name` (1–150), `capacity` (1–50), `price_per_night` (> 0).
- Requires `Authorization: Bearer` (owner only — `403` for anyone else,
  `404` for an unknown listing) **and** an `Idempotency-Key` (min 8 chars).
- The key is stored on the room (`UniqueConstraint(listing_id,
  idempotency_key)`), so replaying a create returns the original room with
  `201`, exactly like listing creation (ADR 0002 pattern).
- Returns `RoomResponse`.

Host dashboard (`app/templates/host_dashboard.html`): each listing row shows
its rooms (name · capacity · price) and an **افزودن اتاق** button that opens a
small form for that listing; submitting it posts the room and reloads the list.

## 2. Listing detail page (guest)

- `GET /api/v1/listings/{listing_id}` — public detail read. Published listings
  only (`404` otherwise), includes `rooms`.
- `GET /listings/{listing_id}` — renders `app/templates/listing_detail.html`
  (Coffee & Cream, offline). Shows title, city, address, description, the room
  list and a booking form: room select, check-in, check-out, **ثبت رزرو**.
- The homepage card button becomes a link to that page and is relabelled
  **مشاهده و رزرو**.

## 3. Booking model and API

`Booking`: `id`, `room_id` (FK rooms, CASCADE), `guest_id` (FK users,
CASCADE), `check_in`, `check_out` (`Date` — calendar dates, no time of day, so
no timezone conversion applies), `status` (`pending` default, `confirmed`,
`cancelled`), `created_at` (UTC `DateTime`), `idempotency_key`.

`POST /api/v1/bookings`

- Body: `room_id`, `check_in`, `check_out`; requires `Authorization` and an
  `Idempotency-Key` (stored, `UniqueConstraint(guest_id, idempotency_key)`).
- `404` unknown room, or a room whose listing is not published.
- `422` when `check_out <= check_in` or `check_in` is in the past.
- `409` when the stay overlaps an existing `pending`/`confirmed` booking of
  that room (`check_in < new.check_out AND check_out > new.check_in` — adjacent
  stays that only share a boundary are allowed).
- `201` with `status = "pending"` and `guest_id = current user`.

**Double booking:** the overlap test is a single SQL statement inside the
booking transaction. It is a pre-flight guard, not the final guarantee —
Iron Rule 2 requires PostgreSQL `EXCLUDE USING gist` in production, and SQLite
cannot express it. ADR 0005 records the constraint that must be added with the
first PostgreSQL deployment, and why the app check exists in the meantime.

## Out of scope

Booking list/cancel endpoints, payments, room edit/delete, availability
calendar, notifications.
