# Phase 4 — Publishing a listing

## Goal

Let a host take their own draft listing live, so the public homepage (which
reads published listings only) can show it.

## 1. `PATCH /api/v1/listings/{listing_id}/publish`

- Requires `Authorization: Bearer` **and** an `Idempotency-Key` header
  (min 8 chars) — Iron Rule 4 applies to every mutating endpoint.
- `404` when no listing has that id.
- `403` when the caller is not the listing's host (admin included: this is the
  host's own action, see ADR 0004).
- `200` with the listing when it moves `draft` → `published`.
- Publishing an already published listing returns it unchanged with `200`
  (naturally idempotent — no write happens).
- `409` when the listing is `archived`; archiving is not undone by publishing.
- The response is `ListingResponse`, and the row appears in the public
  `GET /api/v1/listings` immediately afterwards.

Datetimes stay UTC in the database; no presentation conversion is added here.

## 2. `GET /api/v1/listings/mine`

The host dashboard needs the caller's own listings, drafts included, and no
such read existed (public = published only, `/admin` = admin only).
Returns every listing whose `host_id` is the authenticated user, newest first.
`401` without a token. Never leaks another host's rows.

## 3. Host dashboard

`app/templates/host_dashboard.html` gains an **اقامتگاه‌های من** section above
the create form: one row per listing with title, city, registration date and a
status chip. Draft rows also get an **انتشار** button which calls the PATCH
endpoint with a generated `Idempotency-Key`, then reloads the list so the row
shows as منتشرشده. Failures surface in the existing alert style; `401` signs
the user out.

## Out of scope

Unpublish/archive, editing, rooms, bookings, admin publishing on a host's behalf.
