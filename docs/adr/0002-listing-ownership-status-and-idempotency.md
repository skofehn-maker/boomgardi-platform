# ADR 0002 — Listing ownership, status workflow and idempotent creation

- **Status:** Accepted
- **Date:** 2026-11-24
- **Context:** Phase 2 introduces listings and rooms.

## Decision

1. **Ownership is a stored column, not a role.** `listings.host_id` references
   `users.id`; the host is always the authenticated caller. Any authenticated user
   may host — no separate `host` role is required yet.
2. **Status is an explicit string column** limited to `draft`, `published`,
   `archived`, defaulting to `draft`. Only `GET /api/v1/listings` filters on it
   (`published`), so nothing leaks into the public list by default.
3. **Idempotency is persisted on the listing.** Because Iron Rule 4 requires an
   `Idempotency-Key` on every mutating endpoint, the key is stored in
   `listings.idempotency_key` with a unique constraint on `(host_id, idempotency_key)`.
   A replay from the same host returns the previously created listing instead of a
   duplicate; the same key from a different host is independent.
4. **Rooms belong to a listing** with `ON DELETE CASCADE` and are loaded eagerly
   (`lazy="selectin"`) so responses can embed them without async lazy-load errors.

## Consequences

- Publishing needs a later endpoint (not in Phase 2); today a listing can only be
  published by direct data change or in a future release.
- Deferring a dedicated idempotency table keeps the schema small; if more mutating
  endpoints appear, the column approach can be generalised into an
  `idempotency_keys` table without changing the API contract.
- Because `host_id` cascades on delete, removing a user removes their listings and
  their rooms transitively.
