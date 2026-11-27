# ADR 0011 — The exclusion constraint lives in the migration, not the model

## Status

Accepted (phase 13).

## Context

Iron Rule 2 requires double-booking prevention to be a PostgreSQL
`EXCLUDE USING gist` constraint. The application also runs on SQLite for
development and tests, where the schema is created from `Base.metadata`
(`create_db.py`, the test fixtures), not from Alembic.

SQLAlchemy can describe this constraint with
`sqlalchemy.dialects.postgresql.ExcludeConstraint`, but it is a
PostgreSQL-only DDL construct: SQLite's DDL compiler cannot render it, so
`Base.metadata.create_all()` would fail on every development database and in
every test fixture.

## Decision

1. The constraint is created by Alembic (`0001`, hardened idempotently by
   `0002`) and is the production guarantee.
2. The model declares everything SQLite can enforce — foreign keys,
   `UniqueConstraint`, `Index` and `CheckConstraint("check_out > check_in")` —
   but not the exclusion constraint.
3. `0002` creates the constraint only when `pg_constraint` has no row for it,
   so applying it after `0001` (or to a database created by hand with the
   constraint) is safe, and re-running `upgrade` after a partial failure is
   safe too.
4. The API keeps its single-statement overlap query. It is a UX pre-check and
   the only protection available on SQLite; on PostgreSQL the constraint is
   the source of truth and an overlap that slips past the check still fails
   the transaction.

## Consequences

- Development and tests keep working on SQLite.
- `alembic upgrade head` on PostgreSQL produces the guarantee even if `0001`
  already ran.
- A model-driven `create_all()` against PostgreSQL would **not** create the
  constraint. Production must therefore be migrated with Alembic, which is
  already the project rule.
- The constraint is verified here by offline SQL rendering only; a PostgreSQL
  integration test remains outstanding and is recorded in ADR 0005 as well.
