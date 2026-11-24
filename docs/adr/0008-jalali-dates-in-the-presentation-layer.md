# ADR 0008 — Jalali dates live in the presentation layer only

- **Status:** Accepted
- **Date:** 2026-11-24

## Context

Iranian users read and type Shamsi dates, but every stored `check_in` /
`check_out` is a calendar `DATE` in the Gregorian calendar, and the Postgres
exclusion constraint and all API contracts depend on that. Two problems showed
up in the UI:

1. `<input type="date">` renders and parses according to the browser locale, so
   a Persian page could show a Gregorian picker, and its submitted value never
   looked like a Shamsi date.
2. `Intl.DateTimeFormat('fa-IR', …)` formats through the browser's ICU data.
   Where the Persian calendar is compiled in it prints `۵ آذر ۱۴۰۳`; where it
   is not, it silently falls back to Gregorian — the reported `2024-11-25`.

Third-party Jalali datepicker CDNs were rejected: this project already had a
CDN dependency fail and the templates must stay fully offline.

## Decision

Convert dates on the client, in one local module (`app/static/js/jalali.js`),
using an inline arithmetic conversion (the widely used 33-year-cycle
Gregorian↔Jalali algorithm). It exposes `window.JalaliDate` and is loaded with a
same-origin `<script src="/static/js/jalali.js">`.

- Storage, schemas, validation and the Postgres exclusion constraint are
  untouched; the API still receives and returns `YYYY-MM-DD`.
- The datepicker keeps the Gregorian value in `data-iso` and shows only the
  Shamsi label, so conversion happens exactly at the UI boundary.
- Display uses the explicit numeric format `۱۴۰۳/۰۹/۰۵`.
- UTC instants (account timestamps, session expiry) keep using
  `Intl` with `Asia/Tehran`, because they are timeline values rather than
  calendar days.

## Consequences

- No CDN, no build step, no new Python/pip dependency.
- The arithmetic conversion is accurate for the supported Jalali range
  (1178–1633 Jalali, roughly 1799–2256) and is covered by the picker's own
  round-trip through `toIso`/`toJalaliFromIso`.
- If a future feature needs Jalali server-side (reports, exports), the same
  module can be mirrored in Python rather than duplicating rules in templates.
- Localized month/day names are deliberately not used for the numeric display
  format; `monthLabel` exists for the picker header only.
