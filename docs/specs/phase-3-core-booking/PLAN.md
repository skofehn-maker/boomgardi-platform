# Phase 3 — PLAN

1. `tests/test_host_inbox.py` — red first:
   - `/host` renders the «رزروهای دریافتی» table (headers مهمان/اتاق/ورود/خروج/
     وضعیت/عملیات) wired to `/api/v1/bookings/host`, with both action endpoints
     present in the page;
   - a guest booking confirmed through the API shows `confirmed` in
     `GET /api/v1/bookings/host`, which is what the table renders.
2. `app/templates/host_dashboard.html`:
   - replace the summary rows with the table + compact table CSS;
   - `bookingRow()` renders status chip and pending-only action buttons;
   - `runBookingAction()` sends the `PATCH` with `Idempotency-Key`, then reloads;
   - keep the existing listings console, room form and publish flow untouched.
3. Update the Phase 7 assertion that looked for the old «رزروهای اخیر» heading.
4. `pytest tests -q`, `compileall`, template sanity (tag balance, no Jinja
   tokens, no external URLs, `node --check` on inline scripts).
5. Browser pass as the host: table renders, تأیید and لغو move the row to
   تأییدشده / لغوشده without a reload.
6. If a mutation is needed at the end, `git add .` + commit + push `dev`.
