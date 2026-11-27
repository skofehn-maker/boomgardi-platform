# Phase 12 — Self-service profile editing

## Goal

Let a signed-in user change their own display name and password, from the
profile page, without an admin.

## Existing behaviour confirmed (search & filter)

`GET /api/v1/listings` already accepts optional `city` (case-insensitive
substring) and `max_price` (a room at or below that nightly price) and only ever
returns published listings. `app/templates/index.html` already renders the city
box, the max-price select and the "جستجو" button, and `loadListings(city,
maxPrice)` re-fetches `/api/v1/listings?...` on submit/change. Covered by
`tests/test_search_and_payments.py`. Nothing to add there.

## Requirements

R1. `PUT /api/v1/users/me` updates the authenticated user's `full_name` and/or
    `password`. At least one field is required; an empty body is rejected.
R2. Both fields are optional and validated: `full_name` ≤ 255 characters
    (blank clears it), `password` 8–128 characters and stored only as a bcrypt
    hash. A password change does not invalidate already-issued tokens.
R3. The endpoint is mutating, so it requires `Idempotency-Key` (Iron Rule 4) and
    a valid bearer token; another user's row can never be targeted — the subject
    always comes from the token.
R4. `app/templates/profile.html` gains an "ویرایش پروفایل" form with a display
    name field, a new-password field and a "ذخیره تغییرات" button. On success it
    patches the cached `current_user.full_name` and the visible name; failures
    show the API's Persian `detail`.

## Design notes

- The update writes absolute values (`full_name = ...`, `password_hash = ...`),
  so replaying the same request with the same key converges on the same state;
  no idempotency table is needed. Recorded in ADR 0010.
- No `current_password` check: the request is already authenticated by the
  access token, matching the scope of this request.

## Out of scope

- Email change (it is the login identifier and needs a verification flow).
- Avatar upload, account deactivation, admin user management.
- A host-specific copy of the form: the host dashboard links to `/profile`,
  which now owns the form.
