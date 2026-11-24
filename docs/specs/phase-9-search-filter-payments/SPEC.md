# Phase 9 — Search & Filtering + Mock Payment / Cancellation

## Goal

1. Guests can search/filter published listings by city and maximum room price.
2. Guests can pay (mock) a pending booking to confirm it, or cancel it, from
   their profile page.

## 1. Search & filter (backend)

`GET /api/v1/listings` accepts optional query parameters:

- `city` (string): case-insensitive substring match on `Listing.city`.
- `max_price` (float): only listings that have at least one room with
  `price_per_night <= max_price`.

When neither is provided, behaviour is unchanged (all published listings).

## 2. Search & filter (frontend)

`app/templates/index.html` gains a search bar: a text input for city and a
price filter (dropdown). A "search" button (and Enter) re-fetches
`/api/v1/listings` with `city` and/or `max_price` query params and re-renders
the grid.

## 3. Mock payment & cancellation (guest profile)

- `PATCH /api/v1/bookings/{id}/pay`: requires `Idempotency-Key`; allowed for
  the booking's guest owner (and the hosting host). Transitions `pending` ->
  `confirmed` (mock successful payment); `cancelled` -> 409; `confirmed` is a
  no-op.
- `PATCH /api/v1/bookings/{id}/cancel`: already exists (host). Ownership is
  extended to the booking's guest owner so a guest can cancel their own
  booking. Transitions to `cancelled`.
- `app/templates/profile.html`: for `pending` bookings render a "پرداخت" (Pay)
  button and a "لغو" (Cancel) button that call the endpoints with an
  `Idempotency-Key` and refresh the list.

## Out of scope

Real payment provider, refunds, partial cancellation, amenities filter,
server-side pagination.
