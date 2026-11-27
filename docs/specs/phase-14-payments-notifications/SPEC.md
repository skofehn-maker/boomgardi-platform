# Phase 14 — Mock payment page and in-app notifications

## Goal

Route paying guests through a dedicated mock gateway page, and tell users when a
booking changes state.

## Requirements

### Payment

R1. `GET /payment/{booking_id}` serves `app/templates/payment.html` (Coffee &
    Cream palette) for a signed-in guest.
R2. The page loads the booking from `/api/v1/bookings/mine`, shows listing,
    city, room, Jalali check-in/check-out and total nights, and offers
    "پرداخت آنلاین".
R3. Pressing it calls `PATCH /api/v1/bookings/{id}/pay` with the bearer token
    and a fresh `Idempotency-Key` (Iron Rule 4), shows a success message, then
    redirects to `/profile`. Already-confirmed bookings show a "already paid"
    notice; cancelled ones show an error; 401 sends the user to `/login`.
R4. `app/templates/profile.html`: the "پرداخت" control navigates to
    `/payment/{id}` instead of calling the pay endpoint itself.

### Notifications

R5. `Notification` model (`app/models/notification.py`): UUID id, `user_id` FK
    to `users.id` (CASCADE, indexed), `message` (500), `is_read` (default
    false), `created_at` UTC server default. Index on `(user_id, is_read)`.
R6. API (`/api/v1/notifications`):
    - `GET /unread` — the caller's unread notifications, newest first.
    - `GET ?limit=` — the caller's latest notifications (1–50, default 10) for
      the dropdown.
    - `PATCH /read` — marks the caller's unread notifications read; requires
      `Idempotency-Key`; returns `{"updated": n}` and is safe to replay.
    Every endpoint is scoped by `current_user.id`; no request may read or
    mutate another user's rows.
R7. Confirming a booking notifies the guest; paying notifies the guest; a
    cancellation notifies the other party (host when the guest cancels, guest
    when the host cancels). Notifications are written in the same transaction
    as the status change and only on an actual transition.
R8. `index.html` and `profile.html` navbars get a bell with the unread count and
    a dropdown of the latest notifications, driven by a shared
    `app/static/js/notifications.js` + `app/static/css/notifications.css`.
    Opening the dropdown marks them read and clears the badge.

## Out of scope

- Real payment provider, amounts charged, receipts, refunds.
- Email/SMS/push delivery, per-notification read endpoints, pagination beyond
  the dropdown limit.
- Rerouting `host_bookings.html`/`host_dashboard.html` navbars to the bell; the
  shared script makes that a one-line addition later.
