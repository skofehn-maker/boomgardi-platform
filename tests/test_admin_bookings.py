"""Phase 13 acceptance tests: PG exclusion guard + admin bookings view.

Written before the implementation (Iron Rule 1). The database is in-memory
SQLite, so the exclusion constraint itself is asserted through the migration
text; the API and model behaviour are exercised for real.
"""

import asyncio
import re
import uuid
from contextlib import asynccontextmanager
from datetime import date, timedelta
from pathlib import Path

from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
from app.core.security import hash_password
from app.main import app
from app.models.booking import Booking
from app.models.listing import Listing, Room
from app.models.user import User

ADMIN = {"email": "admin@boom.local", "password": "Admin@1234"}
HOST = {"email": "host@boom.local", "password": "Host@1234"}
GUEST = {"email": "guest@boom.local", "password": "Guest@1234"}

VERSIONS = Path(__file__).resolve().parents[1] / "alembic" / "versions"


@asynccontextmanager
async def seeded_client():
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with session_factory() as session:
        admin = User(
            email=ADMIN["email"],
            password_hash=hash_password(ADMIN["password"]),
            full_name="مدیر سامانه",
            role="admin",
        )
        host = User(
            email=HOST["email"],
            password_hash=hash_password(HOST["password"]),
            full_name="میزبان یزد",
            role="host",
        )
        guest = User(
            email=GUEST["email"],
            password_hash=hash_password(GUEST["password"]),
            full_name="مهمان کاشان",
            role="guest",
        )
        session.add_all([admin, host, guest])
        await session.flush()

        listing = Listing(
            host_id=host.id,
            title="اقامتگاه باغ ایرانی",
            city="یزد",
            address="یزد، خیابان کاشان",
            status="published",
        )
        session.add(listing)
        await session.flush()

        room = Room(
            listing_id=listing.id,
            name="اتاق گل",
            capacity=2,
            price_per_night=850000,
        )
        session.add(room)
        await session.flush()

        today = date.today()
        session.add_all(
            [
                Booking(
                    room_id=room.id,
                    guest_id=guest.id,
                    check_in=today + timedelta(days=10),
                    check_out=today + timedelta(days=12),
                    status="confirmed",
                ),
                Booking(
                    room_id=room.id,
                    guest_id=guest.id,
                    check_in=today + timedelta(days=20),
                    check_out=today + timedelta(days=22),
                    status="pending",
                ),
                Booking(
                    room_id=room.id,
                    guest_id=guest.id,
                    check_in=today + timedelta(days=30),
                    check_out=today + timedelta(days=31),
                    status="cancelled",
                ),
            ]
        )
        await session.commit()

    async def override_get_db():
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://testserver"
        ) as client:
            yield client
    finally:
        app.dependency_overrides.clear()
        await engine.dispose()


async def _token(client: AsyncClient, credentials: dict) -> str:
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": credentials["email"], "password": credentials["password"]},
    )
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def test_admin_bookings_requires_authentication():
    async def scenario():
        async with seeded_client() as client:
            response = await client.get("/api/v1/bookings/all")
            assert response.status_code == 401, response.text

    asyncio.run(scenario())


def test_admin_bookings_is_closed_to_guests_and_hosts():
    async def scenario():
        async with seeded_client() as client:
            for credentials in (GUEST, HOST):
                token = await _token(client, credentials)
                response = await client.get(
                    "/api/v1/bookings/all",
                    headers={"Authorization": f"Bearer {token}"},
                )
                assert response.status_code == 403, (credentials["email"], response.text)

    asyncio.run(scenario())


def test_admin_sees_every_booking_with_both_parties():
    async def scenario():
        async with seeded_client() as client:
            token = await _token(client, ADMIN)
            response = await client.get(
                "/api/v1/bookings/all",
                headers={"Authorization": f"Bearer {token}"},
            )
            assert response.status_code == 200, response.text

            rows = response.json()
            assert len(rows) == 3
            assert {row["status"] for row in rows} == {"pending", "confirmed", "cancelled"}

            row = rows[0]
            assert row["guest_name"] == "مهمان کاشان"
            assert row["guest_email"] == GUEST["email"]
            assert row["host_name"] == "میزبان یزد"
            assert row["host_email"] == HOST["email"]
            assert row["listing_title"] == "اقامتگاه باغ ایرانی"
            assert row["room_name"] == "اتاق گل"
            assert row["check_in"] and row["check_out"]

    asyncio.run(scenario())


def test_admin_page_exposes_the_bookings_view():
    async def scenario():
        async with seeded_client() as client:
            response = await client.get("/admin")
            assert response.status_code == 200, response.text
            body = response.text

            assert "مدیریت رزروها" in body
            assert "/api/v1/bookings/all" in body
            assert 'id="booking-status-filter"' in body
            for label in ("در انتظار", "تأییدشده", "لغوشده"):
                assert label in body

    asyncio.run(scenario())


def test_booking_relationships_and_date_check_exist():
    assert {"room", "guest"} <= set(Booking.__mapper__.relationships.keys())
    assert "bookings" in Room.__mapper__.relationships

    check_names = {
        constraint.name
        for constraint in Booking.__table__.constraints
        if constraint.__class__.__name__ == "CheckConstraint"
    }
    assert "ck_bookings_dates" in check_names


def test_newest_migration_adds_the_postgres_exclusion_constraint():
    files = sorted(path for path in VERSIONS.glob("0002_*.py"))
    assert files, "expected a new 0002 migration"

    source = files[0].read_text(encoding="utf-8")
    assert "btree_gist" in source
    assert re.search(r"EXCLUDE\s+USING\s+gist", source), source
    assert "daterange(check_in, check_out, '[)')" in source
    assert "WHERE (status IN ('pending', 'confirmed'))" in source
    assert 'down_revision = "0001_booking_no_overlap"' in source
    assert "IF NOT EXISTS" in source
    assert "ck_bookings_dates" in source


def test_balance_data_model_has_no_stale_duplicate_constraint():
    """The migration is the only place the exclusion constraint is declared."""
    model_source = (
        Path(__file__).resolve().parents[1] / "app" / "models" / "booking.py"
    ).read_text(encoding="utf-8")
    assert "ExcludeConstraint" not in model_source

    async def scenario():
        async with seeded_client() as client:
            token = await _token(client, ADMIN)
            mine = await client.get(
                "/api/v1/bookings/mine",
                headers={"Authorization": f"Bearer {token}"},
            )
            assert mine.status_code == 200, mine.text
            assert mine.json() == []

    asyncio.run(scenario())


def test_booking_rows_are_reachable_through_relationships():
    """A booking loaded through the ORM exposes its room and guest."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async def scenario():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        async with session_factory() as session:
            guest = User(
                email="rel@boom.local",
                password_hash=hash_password("Rel@12345"),
                role="guest",
            )
            host = User(
                email="relhost@boom.local",
                password_hash=hash_password("Rel@12345"),
                role="host",
            )
            session.add_all([guest, host])
            await session.flush()

            listing = Listing(
                host_id=host.id, title="اقامتگاه", city="یزد", address="یزد"
            )
            session.add(listing)
            await session.flush()

            room = Room(
                listing_id=listing.id,
                name="اتاق",
                capacity=2,
                price_per_night=100000,
            )
            session.add(room)
            await session.flush()

            booking = Booking(
                room_id=room.id,
                guest_id=guest.id,
                check_in=date.today() + timedelta(days=1),
                check_out=date.today() + timedelta(days=2),
            )
            session.add(booking)
            await session.commit()

        async with session_factory() as session:
            stored = await session.scalar(select(Booking))
            assert stored is not None

            # Async sessions cannot lazy-load on attribute access, so the
            # relationships are preloaded explicitly.
            await session.refresh(stored, ["room", "guest"])
            assert stored.room.name == "اتاق"
            assert stored.guest.email == "rel@boom.local"

            room = await session.get(Room, stored.room_id)
            await session.refresh(room, ["bookings"])
            assert [item.id for item in room.bookings] == [stored.id]

        await engine.dispose()

    asyncio.run(scenario())
