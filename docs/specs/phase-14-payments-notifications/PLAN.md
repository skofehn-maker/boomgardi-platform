# Phase 14 — PLAN

## Steps

1. Failing tests `tests/test_payments_and_notifications.py`:
   - notification model shape and the `(user_id, is_read)` index;
   - pay creates exactly one unread notification for the guest;
   - host confirm notifies the guest; guest cancel notifies the host; host
     cancel notifies the guest; a replayed action adds no second row;
   - `/unread` and the latest list are 401 without a token, return only the
     caller's rows, honour `limit`, and reject bad `limit` values;
   - `PATCH /read` needs `Idempotency-Key`, marks only the caller's rows,
     reports the updated count and returns 0 on replay;
   - `GET /payment/{id}` is 200 and contains "پرداخت آنلاین";
   - `profile.html` links to `/payment/{id}` and has no direct pay action;
   - `index.html` / `profile.html` mount the bell and load the shared assets.
2. Model + `create_db.py`/`alembic/env.py` imports, ADR 0012.
3. `app/schemas/notification.py`, `app/api/v1/notifications.py`, router wiring.
4. `bookings.py`: notification writes inside the existing transitions
   (confirm/pay/cancel), via a small `_notify` helper so the change and the
   notice commit together.
5. `app/templates/payment.html`, `GET /payment/{booking_id}` in `main.py`.
6. `profile.html` pay control becomes a link to the payment page.
7. Shared bell: `static/css/notifications.css`, `static/js/notifications.js`,
   mounts and script tags in `index.html` and `profile.html`.
8. Full `pytest`, then commit and push.

## Iron rules

- Rule 1: SPEC/PLAN + failing tests first.
- Rule 3: `Notification.created_at` is UTC; Jalali rendering stays in the UI.
- Rule 4: `PATCH /notifications/read` requires `Idempotency-Key`; the pay
  endpoint already did, and the payment page now sends a fresh key.
- Rule 6: ADR 0012 records the notification lifecycle and read-all semantics.
- Rule 7: full suite before the commit.

## Verification limit

The pages are client-rendered; pytest proves the API contract, the notification
writes and the markup. The bell dropdown and the payment redirect are not
exercised in a browser here.
