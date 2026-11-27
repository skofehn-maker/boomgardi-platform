# ADR 0012 — In-app notifications are written with the state change

## Status

Accepted (phase 14).

## Context

Users only learn that a booking was confirmed or cancelled by revisiting their
dashboard. A notification row per event fixes that, but it must not desync from
the booking it describes, and it must not leak between accounts.

## Decision

1. `Notification` rows are created inside the same transaction as the booking
   status update (`db.add(...)` before the single `db.commit()`), so a booking
   can never be confirmed without its notice, and a rolled-back update leaves no
   phantom notification.
2. A notice is written only on a real transition. The confirm/pay endpoints
   already skip the write when the status is unchanged, so replaying the same
   `Idempotency-Key` does not stack notifications.
3. Recipients: the guest for `confirmed` (confirm and mock payment), and the
   counterparty for `cancelled` (host if the guest cancelled, guest if the host
   cancelled). The actor does not get a notification about their own click.
4. Read state is a single `is_read` boolean, flipped by
   `PATCH /api/v1/notifications/read`, which marks **all** of the caller's unread
   rows. That is an absolute write ("unread -> read"), so replaying it with the
   same key is harmless and needs no dedup table (same reasoning as ADR 0010).
   The endpoint requires `Idempotency-Key` for uniformity with Iron Rule 4.
5. Every query filters on `user_id == current_user.id`; the client never sends
   a user identifier.
6. Notifications are read-only snapshots of a message string. They carry no
   foreign key to the booking, so deleting a listing or booking does not cascade
   away history the user already saw.

## Consequences

- No background job or queue is needed for in-app notices.
- Marking read is coarse (all or nothing). If per-item read state is wanted, a
  `PATCH /{id}/read` endpoint can be added without a schema change.
- There is no retention policy yet; the table grows with booking activity.
