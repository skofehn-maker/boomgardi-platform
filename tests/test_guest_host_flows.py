"""Phase 11 acceptance tests: guest cancellation and the logged-in navbars.

Written before the implementation (Iron Rule 1). Runs against an in-memory
SQLite database with ``get_db`` overridden, so ``dev.db`` is never touched.
"""

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

HOST = {"email": "host@boom.local", "password": "Host@1234"}
GUEST = {"email": "guest@boom.local", "password": "Guest@1234"}

DAY = date.today() + timedelta(days=12)


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

    ids: dict[str, uuid.UUID] = {}

    async with session_factory() as session:
        host = User(
            email=HOST["email"],
            password_hash=hash_password(HOST["password"]),
            full_name="میزبان بوم",
            role="host",
        )
        guest = User(
            email=GUEST["email"],
            password_hash=hash_password(GUEST["password"]),
            full_name="کاربر مهمان",
            role="guest",
        )
        session.add_all([host, guest])
        await session.flush()

        listing = Listing(
            host_id=host.id,
            title="اقامتگاه کویر",
            city="یزد",
            address="بافت تاریخی یزد",
            status="published",
        )
        session.add(listing)
        await session.flush()

        room = Room(
            listing_id=listing.id, name="اتاق نخل", capacity=2, price_per_night=1200000
        )
        session.add(room)
        await session.flush()

        pending = Booking(
            room_id=room.id,
            guest_id=guest.id,
            check_in=DAY,
            check_out=DAY + timedelta(days=2),
            status="pending",
        )
        confirmed = Booking(
            room_id=room.id,
            guest_id=guest.id,
            check_in=DAY + timedelta(days=5),
            check_out=DAY + timedelta(days=7),
            status="confirmed",
        )
        session.add_all([pending, confirmed])
        await session.commit()

        ids["listing"] = listing.id
        ids["room"] = room.id
        ids["pending"] = pending.id
        ids["confirmed"] = confirmed.id

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


async def _login(client: AsyncClient, credentials: dict) -> str:
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": credentials["email"], "password": credentials["password"]},
    )
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def _headers(token: str, key: str | None = None) -> dict[str, str]:
    headers = {"Authorization": f"Bearer {token}"}
    if key:
        headers["Idempotency-Key"] = key
    return headers


# ---------------------------------------------------------------- guest page


def test_profile_page_renders_the_guest_bookings_section():
    async def scenario():
        async with api_client() as (client, _ids):
            response = await client.get("/profile")
            assert response.status_code == 200, response.text
            body = response.text

            assert "رزروهای من" in body
            assert "/api/v1/bookings/mine" in body
            assert "لغو رزرو" in body
            # Dates are presented in the Jalali calendar.
            assert "/static/js/jalali.js" in body
            # Cancel is offered beyond the pending state.
            assert "status === 'confirmed'" in body

    asyncio.run(scenario())


def test_profile_navbar_shows_profile_and_logout():
    async def scenario():
        async with api_client() as (client, _ids):
            body = (await client.get("/profile")).text
            assert "پروفایل من" in body
            assert "خروج" in body
            assert "ورود / ثبت‌نام" not in body

    asyncio.run(scenario())


# ----------------------------------------------------------------- host page


def test_host_dashboard_offers_room_creation_per_listing():
    async def scenario():
        async with api_client() as (client, _ids):
            response = await client.get("/host")
            assert response.status_code == 200, response.text
            body = response.text

            assert "افزودن اتاق" in body
            assert "/rooms" in body
            assert "price_per_night" in body
            assert "Idempotency-Key" in body

    asyncio.run(scenario())


def test_host_dashboard_navbar_shows_profile_and_logout():
    async def scenario():
        async with api_client() as (client, _ids):
            body = (await client.get("/host")).text
            assert "پروفایل من" in body
            assert "خروج" in body
            assert "ورود / ثبت‌نام" not in body

    asyncio.run(scenario())


# ------------------------------------------------------------------ cancel


def test_guest_cancels_a_confirmed_booking_idempotently():
    async def scenario():
        async with api_client() as (client, ids):
            token = await _login(client, GUEST)
            key = str(uuid.uuid4())

            response = await client.patch(
                f"/api/v1/bookings/{ids['confirmed']}/cancel",
                headers=_headers(token, key),
            )
            assert response.status_code == 200, response.text
            assert response.json()["status"] == "cancelled"

            replay = await client.patch(
                f"/api/v1/bookings/{ids['confirmed']}/cancel",
                headers=_headers(token, key),
            )
            assert replay.status_code == 200, replay.text
            assert replay.json()["status"] == "cancelled"

    asyncio.run(scenario())


def test_pending_booking_still_cancellable_by_its_guest():
    async def scenario():
        async with api_client() as (client, ids):
            token = await _login(client, GUEST)
            response = await client.patch(
                f"/api/v1/bookings/{ids['pending']}/cancel",
                headers=_headers(token, str(uuid.uuid4())),
            )
            assert response.status_code == 200, response.text
            assert response.json()["status"] == "cancelled"

    asyncio.run(scenario())
