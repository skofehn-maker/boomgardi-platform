"""Phase 9 acceptance tests: search/filter + mock payment/cancellation."""

import asyncio
import uuid
from contextlib import asynccontextmanager
from datetime import date, timedelta

from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
from app.core.security import hash_password
from app.main import app
from app.models.booking import Booking
from app.models.listing import Listing, Room
from app.models.user import User


@asynccontextmanager
async def api_client():
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

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

        listing_yazd = Listing(
            host_id=host.id,
            title="اقامتگاه یزد",
            city="یزد",
            address="یزد",
            status="published",
        )
        listing_kashan = Listing(
            host_id=host.id,
            title="اقامتگاه کاشان",
            city="کاشان",
            address="کاشان",
            status="published",
        )
        session.add_all([listing_yazd, listing_kashan])
        await session.flush()

        session.add_all(
            [
                Room(listing_id=listing_yazd.id, name="اتاق یزد", capacity=2, price_per_night=1200000),
                Room(listing_id=listing_kashan.id, name="اتاق کاشان", capacity=2, price_per_night=800000),
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


async def _login(client, email, password):
    response = await client.post(
        "/api/v1/auth/login", json={"email": email, "password": password}
    )
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def _headers(token=None, key=None):
    headers = {}
    if token:
        headers["Authorization"] = "Bearer " + token
    if key:
        headers["Idempotency-Key"] = key
    return headers


def test_listings_filter_by_city():
    async def scenario():
        async with api_client() as client:
            response = await client.get("/api/v1/listings", params={"city": "یزد"})
            assert response.status_code == 200, response.text
            titles = [row["title"] for row in response.json()]
            assert titles == ["اقامتگاه یزد"]

    asyncio.run(scenario())


def test_listings_filter_by_max_price():
    async def scenario():
        async with api_client() as client:
            response = await client.get("/api/v1/listings", params={"max_price": 900000})
            assert response.status_code == 200, response.text
            titles = [row["title"] for row in response.json()]
            assert titles == ["اقامتگاه کاشان"]

    asyncio.run(scenario())


def test_listings_filter_combined():
    async def scenario():
        async with api_client() as client:
            response = await client.get(
                "/api/v1/listings", params={"city": "کاشان", "max_price": 900000}
            )
            assert response.status_code == 200, response.text
            titles = [row["title"] for row in response.json()]
            assert titles == ["اقامتگاه کاشان"]

    asyncio.run(scenario())


# ---- payment / cancellation ----


@asynccontextmanager
async def booking_client():
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    ids = {}
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
            title="اقامتگاه تست",
            city="یزد",
            address="یزد",
            status="published",
        )
        session.add(listing)
        await session.flush()

        room = Room(listing_id=listing.id, name="اتاق", capacity=2, price_per_night=1000000)
        session.add(room)
        await session.flush()

        booking = Booking(
            room_id=room.id,
            guest_id=guest.id,
            check_in=date.today() + timedelta(days=5),
            check_out=date.today() + timedelta(days=7),
            status="pending",
        )
        session.add(booking)
        await session.commit()

        ids["booking"] = booking.id

    async def override_get_db():
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://testserver"
        ) as client:
            yield client, ids
    finally:
        app.dependency_overrides.clear()
        await engine.dispose()


def test_pay_requires_idempotency_key():
    async def scenario():
        async with booking_client() as (client, ids):
            token = await _login(client, "guest@boom.local", "Guest@1234")
            response = await client.patch(
                f"/api/v1/bookings/{ids['booking']}/pay",
                headers=_headers(token),
            )
            assert response.status_code == 422, response.text

    asyncio.run(scenario())


def test_guest_can_pay_pending_booking():
    async def scenario():
        async with booking_client() as (client, ids):
            token = await _login(client, "guest@boom.local", "Guest@1234")
            response = await client.patch(
                f"/api/v1/bookings/{ids['booking']}/pay",
                headers=_headers(token, str(uuid.uuid4())),
            )
            assert response.status_code == 200, response.text
            assert response.json()["status"] == "confirmed"

    asyncio.run(scenario())


def test_guest_can_cancel_own_booking():
    async def scenario():
        async with booking_client() as (client, ids):
            token = await _login(client, "guest@boom.local", "Guest@1234")
            response = await client.patch(
                f"/api/v1/bookings/{ids['booking']}/cancel",
                headers=_headers(token, str(uuid.uuid4())),
            )
            assert response.status_code == 200, response.text
            assert response.json()["status"] == "cancelled"

    asyncio.run(scenario())


def test_pay_cancelled_booking_is_409():
    async def scenario():
        async with booking_client() as (client, ids):
            token = await _login(client, "guest@boom.local", "Guest@1234")
            await client.patch(
                f"/api/v1/bookings/{ids['booking']}/cancel",
                headers=_headers(token, str(uuid.uuid4())),
            )
            response = await client.patch(
                f"/api/v1/bookings/{ids['booking']}/pay",
                headers=_headers(token, str(uuid.uuid4())),
            )
            assert response.status_code == 409, response.text

    asyncio.run(scenario())


def test_profile_page_has_pay_and_cancel_markers():
    async def scenario():
        async with api_client() as client:
            response = await client.get("/profile")
            assert response.status_code == 200, response.text
            body = response.text
            assert "پرداخت" in body
            assert "لغو" in body
            assert "/pay" in body
            assert "/cancel" in body

    asyncio.run(scenario())


def test_index_page_has_search_markers():
    async def scenario():
        async with api_client() as client:
            response = await client.get("/")
            assert response.status_code == 200, response.text
            body = response.text
            assert "city" in body.lower() or "search" in body.lower()
            assert "max" in body.lower() or "price" in body.lower()

    asyncio.run(scenario())
