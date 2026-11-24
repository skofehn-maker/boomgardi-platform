# Phase 2 — Listings and Rooms

## Goal

Let an authenticated user act as a **host**: create an eco-lodge listing (with optional
rooms), keep it as a draft, and expose published listings publicly.

## Scope

In scope:

- `Listing` and `Room` tables (SQLAlchemy 2.0 typed mapping, UUID primary keys).
- Pydantic schemas for creating and reading listings and rooms.
- `POST /api/v1/listings` — host creates a listing, owned by the caller.
- `GET /api/v1/listings` — public list of **published** listings only.
- `GET /host` — host dashboard page (Coffee & Cream theme, internal CSS).
- `create_db.py` creates the new tables.

Out of scope (later phases):

- Editing / deleting listings, publishing workflow endpoint, room endpoints.
- Search, filtering, pagination, images, availability calendar.
- Booking / reservation logic (Phase 3, must use PostgreSQL `EXCLUDE USING gist`).

## Data model

### listings

| column | type | notes |
|---|---|---|
| id | UUID | primary key, `uuid4` |
| host_id | UUID | FK → `users.id`, `ON DELETE CASCADE`, indexed |
| title | String(200) | required |
| description | Text | nullable |
| city | String(100) | required |
| address | String(255) | required |
| status | String(20) | default `draft`; one of `draft`, `published`, `archived` |
| idempotency_key | String(128) | nullable, unique per host |
| created_at | DateTime | server default `now()` (UTC) |

Unique constraint `uq_listings_host_idempotency (host_id, idempotency_key)`.

### rooms

| column | type | notes |
|---|---|---|
| id | UUID | primary key, `uuid4` |
| listing_id | UUID | FK → `listings.id`, `ON DELETE CASCADE`, indexed |
| name | String(150) | required |
| capacity | Integer | required, 1..50 |
| price_per_night | Float | required, > 0 |

## API contract

### `POST /api/v1/listings`

- Auth: `Authorization: Bearer <JWT>` — the caller becomes `host_id`.
- Header: `Idempotency-Key` (8..128 chars) — **required** (Iron Rule 4).
- Body: `ListingCreate` `{title, description?, city, address}`.
- `201` → `ListingResponse` with `status = "draft"`.
- Replaying the same key from the same host returns the same listing (`201`), never a duplicate.
- `401` no/invalid token, `422` missing header or invalid body.

### `GET /api/v1/listings`

- Public, no auth.
- `200` → `ListingResponse[]`, only `status == "published"`, newest `created_at` first, `rooms` included.

### `GET /host`

- Renders `host_dashboard.html` (200). Auth happens client-side via `localStorage` JWT,
  matching the existing `/admin` and `/profile` pages.

## Rules compliance

- **UTC**: all timestamps stored as UTC; the dashboard formats `created_at` with
  `Intl.DateTimeFormat(..., {timeZone: "Asia/Tehran"})` in the browser only.
- **Idempotency**: header required and persisted per host (see ADR 0002).
- **No secrets in code**: JWT secret stays in `.env`.
- **ADR**: 0002 records the ownership/status/idempotency decisions.

## Acceptance criteria

1. `POST /api/v1/listings` without a token returns `401`.
2. `POST /api/v1/listings` without `Idempotency-Key` returns `422`.
3. A valid request creates exactly one row with `host_id` equal to the caller's id and
   `status = "draft"`.
4. Repeating the request with the same key creates no second row.
5. `GET /api/v1/listings` returns published listings and hides drafts.
6. `GET /host` returns 200 and contains the create-listing form.
7. The new tables exist after `python create_db.py`.
