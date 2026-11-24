# ADR 0003 — Admin sees every status, the public homepage sees published only

- Status: accepted
- Date: 2026-11-24

## Context

Phase 2 gave listings a `status` (`draft`, `published`, `archived`) and made the
public `GET /api/v1/listings` return published rows only. Phase 3 needs the admin
panel to show every registered listing, and a guest homepage listing
accommodations.

A single endpoint with a client-supplied `status=all` was considered and
rejected: a query parameter that widens visibility is easy to send from the
browser and hard to keep from leaking drafts.

## Decision

Two read paths with different guards:

- `GET /api/v1/listings` — public, published only. Unchanged contract.
- `GET /api/v1/listings/admin` — `get_current_admin`, every status.

Authorisation lives in the URL/dependency, not in a parameter, so a guest client
cannot widen what it sees. The homepage therefore consumes the public endpoint
and shows an explicit empty state until a listing is published; surfacing drafts
there would require a publish action, which is out of scope for Phase 3.

## Consequences

- The admin table can show drafts without a new schema or migration.
- A draft stays invisible on the homepage until a status-transition endpoint
  exists (planned follow-up). This is intentional, not a bug.
- Any future "show me all listings" caller has to go through an admin dependency
  rather than flipping a flag.
