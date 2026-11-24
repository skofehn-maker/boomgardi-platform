# ADR 0004 — Publish requires an Idempotency-Key but stores no key table

- Status: accepted
- Date: 2026-11-24

## Context

Iron Rule 4 requires every mutating endpoint to take an `Idempotency-Key`.
`POST /api/v1/listings` persists the key on the listing row, backed by
`UniqueConstraint(host_id, idempotency_key)`, so a retried create returns the
original row (ADR 0002).

`PATCH /listings/{id}/publish` cannot reuse that column: a listing already has
the key of its create request, and a publish client generates a fresh key on
every click.

## Decision

The endpoint **requires** the header (same `min_length=8`, `max_length=128`
validation as create) but does not persist it. The operation is idempotent by
construction: the transition is `status -> "published"`, so replaying it on an
already published listing is a no-op that returns `200` and the same body. Two
concurrent publishes both converge on `published`; no duplicate row can be
created because nothing is inserted.

An alternative — a separate `idempotency_keys` table with a request hash and a
stored response — was rejected for now: it buys nothing for a single-field
state transition and adds a write on every click. It becomes worthwhile once an
endpoint creates rows or charges money (bookings), and that is where it should
be introduced.

Ownership is checked against the listing's `host_id`; an admin gets `403` on
another host's listing, because publishing is the host's editorial decision, not
moderation.

## Consequences

- Rule 4 is satisfied at the API boundary; clients must still send a key.
- A publish retried after a network timeout behaves correctly without any
  stored state.
- Archived listings return `409` rather than silently flipping back to
  published.
