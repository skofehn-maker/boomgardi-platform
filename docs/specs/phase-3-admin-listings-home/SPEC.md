# Phase 3 — Seeded roles, admin listings, guest homepage

## Goal

Close out Phase 2 with usable demo data and the two missing read surfaces:

1. Three predictable seed accounts (admin, host, guest).
2. An admin view of **every** listing regardless of status.
3. A public guest homepage that lists bookable accommodations.

## 1. Seed accounts

`seed_user.py` creates (idempotently) exactly three users:

| Email | Password | Role | Full name |
| --- | --- | --- | --- |
| admin@boom.local | Admin@1234 | admin | مدیر سامانه |
| host@boom.local | Host@1234 | host | میزبان بوم |
| guest@boom.local | Guest@1234 | guest | کاربر مهمان |

Re-running the script never duplicates a row: an existing email is updated in
place (name and role, plus the password hash when the stored hash no longer
matches the seed password) and reported as `updated` or `unchanged`.

## 2. Admin listings

`GET /api/v1/listings/admin` returns every listing (draft, published, archived),
newest first. Admin role required: `401` without a token, `403` for a
non-admin. Reuses `ListingResponse`.

`app/templates/admin.html` gains a second view. Clicking **اقامتگاه‌ها** in the
sidebar hides the dashboard view and shows a table with title, city and status
for every registered listing; **داشبورد** returns to the users/KPI view. The
view is loaded lazily on first visit and can be refreshed.

## 3. Guest homepage

`GET /` renders `app/templates/index.html` (Coffee & Cream theme) instead of
redirecting to `/login`. The page fetches `/api/v1/listings`, which by contract
only exposes **published** listings, and renders one card per listing with its
title, city and a reserve button. Empty, loading and error states are included.
Drafts stay invisible to guests — the public contract from Phase 2 is unchanged.

## Out of scope

Booking, room CRUD, a publish/status endpoint, auth on the homepage.
