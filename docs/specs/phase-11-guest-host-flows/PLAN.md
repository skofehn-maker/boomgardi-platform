# Phase 11 — PLAN

## Steps

1. `tests/test_guest_host_flows.py` (written first, must fail):
   - `GET /profile` contains "رزروهای من", "لغو رزرو", "پروفایل من", and fetches
     `/api/v1/bookings/mine`.
   - `GET /host` contains "افزودن اتاق", the `/rooms` POST target, "پروفایل من"
     and "خروج".
   - A guest can `PATCH /api/v1/bookings/{id}/cancel` a **confirmed** booking and
     gets `cancelled`; a replay with the same key is a no-op.
2. `app/templates/profile.html`:
   - nav: "داشبورد" → "پروفایل من" (same `/profile` href, keeps `current`).
   - booking actions render for `pending` **and** `confirmed`; the pay button is
     only built for `pending`; the cancel button reads "لغو رزرو".
3. `app/templates/host_dashboard.html`: nav "داشبورد" → "پروفایل من".
4. `app/templates/index.html`: no change — the token-driven swap already shows
   "پروفایل من" and "خروج" for a live session.
5. Run the new file, then the full suite; commit and push.

## Iron rules

- Rule 1: SPEC + PLAN + failing test precede code (this directory + step 1).
- Rule 3: dates stay UTC on the wire; `JalaliDate.format` / `Intl` with
  `timeZone: "Asia/Tehran"` do the presentation.
- Rule 4: the cancel request already sends `Idempotency-Key` from
  `makeIdempotencyKey()`.
- Rule 6: no architectural decision is introduced (no new endpoint, table or
  dependency), so no new ADR.
- Rule 7: `pytest` runs before the commit.

## Risk

The dashboards are client-rendered, so tests can only assert markup and the API
contract, not the rendered DOM. That limitation is reported, not papered over.
