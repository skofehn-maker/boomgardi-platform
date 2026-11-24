# ADR 0005 — Overlap guard now, PostgreSQL exclusion constraint before production

- Status: accepted (with a known gap)
- Date: 2026-11-24

## Context

Iron Rule 2 says double-booking prevention must be a PostgreSQL
`EXCLUDE USING gist` constraint, never application logic. The project runs on
SQLite for development and tests (AGENTS.md), and SQLite has no exclusion
constraints, so the rule cannot be satisfied by the dev database.

## Decision

Today `POST /api/v1/bookings` runs one SQL overlap test inside its transaction:

```sql
SELECT 1 FROM bookings
 WHERE room_id = :room_id
   AND status IN ('pending','confirmed')
   AND check_in  < :new_check_out
   AND check_out > :new_check_in
 LIMIT 1
```

If it finds a row the request is refused with `409`. Adjacent stays
(`check_out == check_in`) do not overlap, which is why the comparison is strict.
The check is expressed as SQL, not by iterating loaded rows in Python, so it
stays one statement and behaves the same on both dialects.

This is a **pre-flight guard for UX and for SQLite's single-writer dev
database; it is not the production guarantee.** Under concurrent requests on
PostgreSQL two transactions can both pass the check before either commits.

The guarantee must be added with the first PostgreSQL deployment, in the
Alembic migration that introduces production:

```sql
CREATE EXTENSION IF NOT EXISTS btree_gist;

ALTER TABLE bookings
  ADD CONSTRAINT no_overlapping_bookings
  EXCLUDE USING gist (
    room_id WITH =,
    daterange(check_in, check_out, '[)') WITH &&
  )
  WHERE (status IN ('pending', 'confirmed'));
```

The half-open `'[)'` range matches the API's strict comparisons, and the
partial predicate keeps cancelled bookings from blocking later stays.

## Consequences

- Development and tests exercise the real refusal path; a duplicate is
  impossible in practice on SQLite because writes are serialised.
- Production is **not** safe until the constraint above exists — the app check
  remains as a friendlier error, not as the source of truth.
- Tests would need a PostgreSQL-tagged case for the constraint itself; the
  suite is SQLite-only today, so that is deferred with the constraint.

## Dates

`check_in` / `check_out` are `Date` columns: a stay is a pair of calendar days,
not instants, so Iron Rule 3 (UTC storage) has nothing to convert. `created_at`
is a UTC `DateTime` like every other timestamp.
