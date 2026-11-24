"""bookings: no overlapping stays per room (PostgreSQL only)

Revision ID: 0001_booking_no_overlap
Revises:
Create Date: 2026-11-24

Iron Rule 2: double-booking prevention belongs in the database, as a
PostgreSQL exclusion constraint. SQLite cannot express it, so this migration
records a log line and does nothing there; development keeps the app-level
pre-check (see ADR 0005/0006).

Why ``daterange`` and not ``tstzrange``: ``check_in`` / ``check_out`` are DATE
columns, and expressions inside an exclusion constraint must be immutable.
``date`` -> ``timestamptz`` depends on the session TimeZone and is therefore
only *stable*, which PostgreSQL rejects here. A ``daterange`` is also the
honest type for a calendar-day stay.

The half-open ``'[)'`` range matches the API's strict comparisons
(``check_in < new_check_out AND check_out > new_check_in``): a guest checking
out on the day the next guest checks in does not overlap.

Prerequisite: the table schema is created by ``python create_db.py``. Run this
migration on a database where ``bookings`` already exists.
"""

from alembic import op

revision = "0001_booking_no_overlap"
down_revision = None
branch_labels = None
depends_on = None

CONSTRAINT_NAME = "no_overlapping_bookings"


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    if dialect != "postgresql":
        print(
            f"alembic: skipping {CONSTRAINT_NAME} on {dialect}; "
            "EXCLUDE USING gist requires PostgreSQL. "
            "Development keeps the application-level overlap check."
        )
        return

    op.execute("CREATE EXTENSION IF NOT EXISTS btree_gist")
    op.execute(
        f"""
        ALTER TABLE bookings
          ADD CONSTRAINT {CONSTRAINT_NAME}
          EXCLUDE USING gist (
            room_id WITH =,
            daterange(check_in, check_out, '[)') WITH &&
          )
          WHERE (status IN ('pending', 'confirmed'))
        """
    )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    op.execute(f"ALTER TABLE bookings DROP CONSTRAINT IF EXISTS {CONSTRAINT_NAME}")
