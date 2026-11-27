# Phase 10 — Registration Page

## Goal
A guest or host can create an account from the public site instead of relying on
seeded demo users.

## Scope
- `POST /api/v1/auth/register` accepts optional `full_name` and `role`.
  - `role` is restricted to `guest` or `host`; anything else is rejected with 422.
  - When omitted, the existing default (`guest`) is kept.
- `GET /register` renders `app/templates/register.html`.
- `login.html` links to `/register`; `register.html` links back to `/login`.

## Out of scope
- Email verification, password reset, admin-created users.
- Role changes after registration (admin API already covers user management).

## Constraints
- Templates stay offline: internal CSS only, no external fonts or CDNs.
- Coffee & Cream palette: `#f5f0e6`, `#fdfbf7`, `#d7ccc8`, `#6f4e37`, `#4e342e`, `#3e2723`.
- Persian, RTL, `dir="rtl"`, Vazirmatn/Segoe UI/Tahoma fallbacks.
- The API stores everything in UTC; this page has no datetimes.
