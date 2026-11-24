# Phase 8 — PLAN

1. `tests/test_persian_dates.py` — red first:
   - `/static/js/jalali.js` is served locally with the conversion functions and
     no `http(s)://` reference;
   - `/listings/{id}` has no `type="date"`, links the module, renders both
     calendar popups and posts ISO values back (`toIso`);
   - the four booking pages link the module, format via `JalaliDate.format(`
     and no longer hand-parse `… + 'T00:00:00Z'` for display.
2. `app/static/js/jalali.js` — conversion, Persian digits, month lengths,
   `monthLabel`, `todayIso`.
3. `listing_detail.html` — read-only Shamsi inputs + `data-iso`, calendar
   popup markup, picker script, submit/summary read the ISO attribute.
4. `profile.html`, `host_dashboard.html`, `host_bookings.html`,
   `profile_bookings.html` — load the module and format stay dates with it.
5. pytest, `node --check` on the new static module, template sanity, browser
   pass through booking + both dashboards.
6. Commit `feat: add Persian (Jalali) date support for booking UI`, push `dev`.
