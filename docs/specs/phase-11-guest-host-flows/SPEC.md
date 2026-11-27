# Phase 11 — Guest bookings & host room management (completion)

## Goal

Close the remaining gaps in the guest and host dashboards so the two flows are
usable end to end, without adding new API surface.

## Current state (verified)

- `GET /api/v1/bookings/mine` returns the caller's bookings with `listing_title`,
  `listing_city`, `room_name`, `check_in`, `check_out` and `status`.
- `PATCH /api/v1/bookings/{id}/cancel` exists and accepts the booking's guest or
  the hosting host. It is idempotent and requires `Idempotency-Key`.
- `app/templates/profile.html` already renders "رزروهای من" from `/mine`, with
  Persian (Jalali) dates and a status badge.
- `app/templates/host_dashboard.html` (served at `/host`) already lists the
  host's listings with an "افزودن اتاق" button per row and a form that POSTs
  `{name, capacity, price_per_night}` to `/api/v1/listings/{id}/rooms` with an
  `Idempotency-Key`.

So no new endpoints and no new templates are needed. Three defects remain.

## Requirements

R1. A guest must be able to cancel **pending and confirmed** bookings from
    "رزروهای من"; the action label is exactly "لغو رزرو". Paying stays available
    only while the booking is pending.

R2. The logged-in navbar on `profile.html` and the host dashboard must offer
    "پروفایل من" (link to `/profile`) and "خروج" (logout), not a login/register
    prompt. `index.html` already swaps `ورود / ثبت‌نام` for `پروفایل من` +
    `خروج` from the stored token; it is verified, not changed.

R3. `app/templates/host.html` does not exist. The host page is
    `app/templates/host_dashboard.html`, served by `GET /host`. Creating a second
    `host.html` would add a dead template, so the host changes land in the file
    that is actually rendered.

## Out of scope

- New listing/room CRUD endpoints, edit/delete, image upload.
- Server-side rendering of the dashboards (they stay token-driven SPA pages).
- Changing the cancel authorization rules (guest owner or hosting host).
