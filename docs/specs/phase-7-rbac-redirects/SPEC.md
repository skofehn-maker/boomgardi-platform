# Phase 7 — Role-based landing after login

## Goal

Every role lands on the dashboard that belongs to it, the host dashboard reads
as an operator console, and the profile page tells the truth about the role and
shows the user's bookings.

## 1. Login response

`POST /api/v1/auth/login` gains a top-level `role` next to the token:

```json
{"access_token": "...", "token_type": "bearer", "expires_in": 1800,
 "role": "host", "user": {"...": "..."}}
```

`user`, `expires_in` and `token_type` stay as they are — the templates and the
existing tests read them.

## 2. Redirect by role (`login.html`)

One map governs both entry points (already-signed-in bootstrap and a fresh
login): `admin → /admin`, `host → /host`, `guest → /profile`, anything unknown
falls back to `/profile`. The role is read from `payload.role`, then
`payload.user.role`, then the JWT claim.

## 3. Host dashboard

`/host` already lists the host's listings, their rooms, the create form and the
publish action. It gains a **رزروهای اخیر** panel fed by
`GET /api/v1/bookings/host` (latest three, with guest, dates and status) and a
link to the full `/host/bookings` inbox, so the page reads as a console rather
than a profile.

## 4. Profile page

- **Role bug:** the label was `admin ? 'مدیر سامانه' : 'کاربر مهمان'`, so a host
  was shown as a guest. It becomes a map (`admin`, `host`, `guest`) used by the
  badge, the stat and the details row.
- **رزروهای من:** a section fed by `GET /api/v1/bookings/mine` listing each
  booking's listing, room, dates and status, with empty/error states and a link
  to `/profile/bookings`.

## Out of scope

Server-side page guards (pages are still client-guarded), role editing,
permission matrices beyond admin/host/guest landing pages.
