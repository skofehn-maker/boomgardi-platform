# Phase 3 — Core booking: host inbox with actions

## Context

The double-booking guard (Iron Rule 2) and the guest bookings page are already
delivered:

- `alembic/versions/0001_booking_no_overlap.py` adds `btree_gist` and
  `EXCLUDE USING gist (...)` on `bookings` (see the note below on `daterange`
  versus `tstzrange`);
- `PATCH /api/v1/bookings/{id}/confirm` and `/{id}/cancel` exist and are
  covered by `tests/test_bookings_flow.py`;
- the guest page (`/profile`) has a «رزروهای من» section fed by
  `/api/v1/bookings/mine`.

What is missing is the host page itself: `/host` shows only a text summary of
recent bookings, so a host must open `/host/bookings` to confirm or cancel
anything. This phase puts the inbox — with working actions — on the dashboard.

## 1. «رزروهای دریافتی» table on `/host`

A real table under the listing list, fed by `GET /api/v1/bookings/host`:

| مهمان | اتاق | ورود | خروج | وضعیت | عملیات |

- guest name with the e-mail underneath, room name, both dates (fa-IR),
  a status chip (در انتظار تأیید / تأییدشده / لغوشده);
- **تأیید** and **لغو** buttons appear only for `pending` bookings, sending
  `PATCH /api/v1/bookings/{id}/confirm` and `/{id}/cancel` with the
  `Idempotency-Key` header the API requires;
- the table reloads from the API after every action, so the row shows the new
  status, and clears the action buttons;
- «همه رزروها» links to the full `/host/bookings` inbox;
- empty, error and loading states are handled; `401` signs the host out.

## 2. Migration form (`tstzrange` vs `daterange`)

The requested form is `tstzrange(check_in, check_out) WITH &&`. `check_in` and
`check_out` are `DATE` columns, and expressions inside an exclusion constraint
must be **immutable**; `date → timestamptz` depends on the session `TimeZone`
and is only *stable*, so PostgreSQL rejects that constraint with
`functions in index expression must be marked IMMUTABLE`.

`daterange(check_in, check_out, '[)')` is the immutable, date-exact equivalent
for calendar-day stays and is what migration `0001` creates (ADR 0006). The
`tstzrange` form only becomes available if the columns are migrated to
`timestamptz`; that is a schema decision with API impact and is left as an
explicit follow-up.

## Out of scope

Changing `check_in`/`check_out` column types, guest-side cancellation, pagination
of the host inbox (the full `/host/bookings` page already lists everything).
