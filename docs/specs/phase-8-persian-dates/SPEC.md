# Phase 8 — Persian (Jalali) dates in the booking UI

## Goal

Every booking date a person types or reads is Shamsi (`۱۴۰۳/۰۹/۰۵`). The
database, the API and the models keep storing Gregorian calendar dates
(`DATE` columns, `YYYY-MM-DD` in JSON) — this phase is presentation only.

## 1. One local conversion module

`app/static/js/jalali.js` is served by the existing `/static` mount and exposes
`window.JalaliDate`:

| Function | Meaning |
| --- | --- |
| `toJalali(gy, gm, gd)` | Gregorian parts → `{jy, jm, jd}` |
| `toGregorian(jy, jm, jd)` | Jalali parts → `{gy, gm, gd}` |
| `toIso(jy, jm, jd)` | Jalali parts → `YYYY-MM-DD` for the API |
| `toJalaliFromIso(iso)` | `YYYY-MM-DD` → Jalali parts |
| `format(iso)` | `YYYY-MM-DD` → `۱۴۰۳/۰۹/۰۵` (Persian digits) |
| `monthLength(jy, jm)` | 31 / 30 / 29 for the requested month |
| `todayIso()` | Today's Gregorian date, for `min` bounds |

No CDN, no build step, no framework: the arithmetic 33-year-cycle conversion is
inline and works offline (ADR 0008).

## 2. Persian datepicker on the listing page

`/listings/{id}` no longer renders `<input type="date">` — a browser-native date
input follows the browser locale, not the page. Each stay date becomes:

- a read-only text input that shows the selected date as `۱۴۰۳/۰۹/۰۵`;
- a `data-iso` attribute holding the Gregorian value that is posted;
- a calendar popup (`#check-in-calendar`, `#check-out-calendar`) with Jalali
  month navigation, Saturday-first weekday headers and Persian digits.

Rules enforced in the picker:

- check-in cannot be before today; check-out cannot be before check-in + 1 day;
- picking a check-in that reaches past the current check-out clears check-out;
- the request body still sends `check_in` / `check_out` as `YYYY-MM-DD`, so no
  API, schema, model or migration changes.

## 3. Shamsi display on the dashboards

`/profile` (رزروهای من), `/profile/bookings`, `/host` (رزروهای دریافتی) and
`/host/bookings` render `JalaliDate.format(booking.check_in)` instead of
`Intl.DateTimeFormat('fa-IR', …)`. The `Intl` output depended on the browser's
ICU data (it can fall back to Gregorian), and it printed `۵ آذر ۱۴۰۳` rather
than the requested `۱۴۰۳/۰۹/۰۵`.

Account timestamps (joined date, session expiry) keep their existing
`fa-IR` + `Asia/Tehran` formatting, which is correct for UTC instants.

## Out of scope

Server-side Jalali fields, Jalali month names in reports, changing stored dates,
holiday highlighting, timezone changes.
