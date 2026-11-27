"""bookings: harden the PostgreSQL overlap guard and add the date check

Revision ID: 0002_booking_guard_and_relationships
Revises: 0001_booking_no_overlap
Create Date: 2026-11-27

Iron Rule 2 puts double-booking prevention in the database. ``0001`` added the
constraint, but a plain ``ADD CONSTRAINT`` fails when the constraint is already
present (a database that ran ``0001``, or one created by hand). This revision
makes the guard re-appliable and adds the ``check_out > check_in`` check that
the ORM declares on SQLite (ADR 0011).

Both statements are guarded through ``pg_constraint``, so applying this
migration to a database in either state is safe.

SQLite keeps the application-level pre-check: exclusion constraints are a
PostgreSQL feature. This migration only prints a note there.
"""

from alembic import op

revision = "0002_booking_guard_and_relationships"
down_revision = "0001_booking_no_overlap"
branch_labels = None
depends_on = None

OVERLAP_CONSTRAINT = "no_overlapping_bookings"
DATES_CONSTRAINT = "ck_bookings_dates"

GUARD_SQL = f"""
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
      FROM pg_constraint
     WHERE conname = '{OVERLAP_CONSTRAINT}'
       AND conrelid = 'bookings'::regclass
  ) THEN
    ALTER TABLE bookings
      ADD CONSTRAINT {OVERLAP_CONSTRAINT}
      EXCLUDE USING gist (
        room_id WITH =,
        daterange(check_in, check_out, '[)') WITH &&
      )
      WHERE (status IN ('pending', 'confirmed'));
  END IF;
END
$$;
"""

DATES_SQL = f"""
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
      FROM pg_constraint
     WHERE conname = '{DATES_CONSTRAINT}'
       AND conrelid = 'bookings'::regclass
  ) THEN
    ALTER TABLE bookings
      ADD CONSTRAINT {DATES_CONSTRAINT} CHECK (check_out > check_in);
  END IF;
END
$$;
"""


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        print(
            "alembic: skipping the bookings exclusion constraint on "
            f"{bind.dialect.name}; EXCLUDE USING gist requires PostgreSQL. "
            "Development keeps the application-level overlap check."
        )
        return

    # daterange overlap needs the GiST equality operator for uuid room_id.
    op.execute("CREATE EXTENSION IF NOT EXISTS btree_gist")
    op.execute(GUARD_SQL)
    op.execute(DATES_SQL)


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    op.execute(
        f"ALTER TABLE bookings DROP CONSTRAINT IF EXISTS {DATES_CONSTRAINT}"
    )
    op.execute(
        f"ALTER TABLE bookings DROP CONSTRAINT IF EXISTS {OVERLAP_CONSTRAINT}"
    )
