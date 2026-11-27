# ADR 0010 — Self-service profile update and its idempotency

## Status

Accepted (phase 12).

## Context

Users need to change their own display name and password. The mutation is
`PUT /api/v1/users/me`. Iron Rule 4 requires an `Idempotency-Key` on every
mutating endpoint, which elsewhere (bookings, listings, rooms) is enforced by
persisting the key on the row and returning the original record on replay.

## Decision

`PUT /api/v1/users/me` requires `Idempotency-Key` but stores no dedup record.

The endpoint performs an absolute write: `full_name` is set to the submitted
value and `password_hash` to the hash of the submitted password. Replaying the
same body therefore produces the same observable state; a retried request after
a dropped response cannot double-apply anything, because there is no increment,
append or state transition involved. The key is validated for presence and shape
so that every mutating call site is uniform and a future non-idempotent profile
field (for example email with verification) can add a dedup store without
changing the contract.

## Consequences

- The header requirement is uniform across the API and testable.
- No new table or column; no migration.
- If a future field makes the write relative (e.g. counters, history), this ADR
  must be superseded with a stored-key approach.
