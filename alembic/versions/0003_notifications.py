"""notifications table (phase 14)

Revision ID: 0003_notifications
Revises: 0002_booking_guard_and_relationships
Create Date: 2026-11-27

The ORM creates this table in development through ``create_db.py``; the
migration exists so a PostgreSQL database can be brought to the same schema
with Alembic. It is a no-op when the table is already there.
"""

import sqlalchemy as sa
from alembic import context, op

revision = "0003_notifications"
down_revision = "0002_booking_guard_and_relationships"
branch_labels = None
depends_on = None


def _create_notifications() -> None:
    op.create_table(
        "notifications",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("message", sa.String(length=500), nullable=False),
        sa.Column("is_read", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column(
            "created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_notifications_user_is_read", "notifications", ["user_id", "is_read"]
    )


def _drop_notifications() -> None:
    op.drop_index("ix_notifications_user_is_read", table_name="notifications")
    op.drop_table("notifications")


def upgrade() -> None:
    if context.is_offline_mode():
        # ``alembic upgrade --sql`` has no connection to inspect, and must
        # still render the DDL.
        _create_notifications()
        return

    bind = op.get_bind()
    if "notifications" in sa.inspect(bind).get_table_names():
        print("alembic: notifications already exists; nothing to do.")
        return

    _create_notifications()


def downgrade() -> None:
    if context.is_offline_mode():
        _drop_notifications()
        return

    bind = op.get_bind()
    if "notifications" not in sa.inspect(bind).get_table_names():
        return

    _drop_notifications()
