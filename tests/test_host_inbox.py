"""Phase 3 acceptance tests: the host dashboard's incoming-bookings table.

Written before the implementation (Iron Rule 1). Runs against an in-memory
SQLite database with ``get_db`` overridden, so ``dev.db`` is never touched.
"""

import asyncio
from contextlib import asynccontextmanager
from datetime import date, timedelta

from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
from app.core.security import hash_password
from app.main import app
from app.models.listing import Listing, Room
from app.models.user import User


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

    room_id = None
    async with session_factory() as session:
        host = User(
            email="host@boom.local",
            password_hash=hash_password("Host@1234"),
            full_name="میزبان بوم",
            role="host",
        )
        guest = User(
            email="guest@boom.local",
            password_hash=hash_password("Guest@1234"),
            full_name="کاربر مهمان",
            role="guest",
        )
        session.add_all([host, guest])
        await session.flush()

        listing = Listing(
            host_id=host.id,
            title="اقامتگاه کویر خور",
            city="خور",
            address="کویر خور",
            status="published",
        )
        session.add(listing)
        await session.flush()

        room = Room(
            listing_id=listing.id, name="اتاق نخل", capacity=2, price_per_night=1450000
        )
        session.add(room)
        await session.commit()
        room_id = room.id

    async def override_get_db():
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://testserver"
        ) as client:
            yield client, room_id
    finally:
        app.dependency_overrides.clear()
        await engine.dispose()


async def token_for(client, email: str, password: str) -> str:
    response = await client.post(
        "/api/v1/auth/login", json={"email": email, "password": password}
    )
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def test_host_dashboard_renders_the_incoming_bookings_table():
    async def scenario():
        async with seeded_client() as (client, _room_id):
            response = await client.get("/host")
            assert response.status_code == 200, response.text
            body = response.text

            assert "رزروهای دریافتی" in body
            for header in ("مهمان", "اتاق", "ورود", "خروج", "وضعیت", "عملیات"):
                assert header in body

            assert 'id="host-recent-bookings"' in body
            assert "/api/v1/bookings/host" in body

            # Both actions are wired from this page, not only from /host/bookings.
            assert "/confirm" in body
            assert "/cancel" in body
            assert 'data-booking-action="confirm"' in body
            assert 'data-booking-action="cancel"' in body
            assert "Idempotency-Key" in body

            # The listings console is still intact.
            assert 'id="my-listings-body"' in body
            assert 'id="listing-form"' in body

    asyncio.run(scenario())


def test_confirming_a_booking_is_what_the_table_reads_back():
    async def scenario():
        async with seeded_client() as (client, room_id):
            guest_token = await token_for(client, "guest@boom.local", "Guest@1234")
            host_token = await token_for(client, "host@boom.local", "Host@1234")

            start = date.today() + timedelta(days=10)
            created = await client.post(
                "/api/v1/bookings",
                json={
                    "room_id": str(room_id),
                    "check_in": start.isoformat(),
                    "check_out": (start + timedelta(days=2)).isoformat(),
                },
                headers={
                    "Authorization": "Bearer " + guest_token,
                    "Idempotency-Key": "phase3-host-inbox-0001",
                },
            )
            assert created.status_code == 201, created.text
            booking_id = created.json()["id"]

            inbox = await client.get(
                "/api/v1/bookings/host",
                headers={"Authorization": "Bearer " + host_token},
            )
            assert inbox.status_code == 200, inbox.text
            rows = inbox.json()
            assert [row["status"] for row in rows] == ["pending"]
            assert rows[0]["guest_email"] == "guest@boom.local"
            assert rows[0]["room_name"] == "اتاق نخل"

            confirmed = await client.patch(
                f"/api/v1/bookings/{booking_id}/confirm",
                headers={
                    "Authorization": "Bearer " + host_token,
                    "Idempotency-Key": "phase3-host-inbox-0001-confirm",
                },
            )
            assert confirmed.status_code == 200, confirmed.text
            assert confirmed.json()["status"] == "confirmed"

            after = await client.get(
                "/api/v1/bookings/host",
                headers={"Authorization": "Bearer " + host_token},
            )
            assert [row["status"] for row in after.json()] == ["confirmed"]

            cancelled = await client.patch(
                f"/api/v1/bookings/{booking_id}/cancel",
                headers={
                    "Authorization": "Bearer " + host_token,
                    "Idempotency-Key": "phase3-host-inbox-0001-cancel",
                },
            )
            assert cancelled.status_code == 200, cancelled.text
            assert cancelled.json()["status"] == "cancelled"

    asyncio.run(scenario())
