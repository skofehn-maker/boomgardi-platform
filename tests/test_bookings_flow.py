"""Phase 6 acceptance tests: host/guest booking inboxes and the PG guard.

Written before the implementation (Iron Rule 1). Runs against an in-memory
SQLite database with ``get_db`` overridden, so ``dev.db`` is never touched.
"""

import asyncio
import uuid
from contextlib import asynccontextmanager
from datetime import date, timedelta
from pathlib import Path

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
OTHER_HOST = {"email": "other@boom.local", "password": "Other@1234"}
GUEST = {"email": "guest@boom.local", "password": "Guest@1234"}
OTHER_GUEST = {"email": "guest2@boom.local", "password": "Guest@1234"}

LISTING_TITLE = "اقامتگاه منتشرشده کویر"
ROOM_NAME = "اتاق نخل"
DAY = date.today() + timedelta(days=10)


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
        other = User(
            email=OTHER_HOST["email"],
            password_hash=hash_password(OTHER_HOST["password"]),
            full_name="میزبان دیگر",
            role="host",
        )
        guest = User(
            email=GUEST["email"],
            password_hash=hash_password(GUEST["password"]),
            full_name="کاربر مهمان",
            role="guest",
        )
        other_guest = User(
            email=OTHER_GUEST["email"],
            password_hash=hash_password(OTHER_GUEST["password"]),
            full_name="مهمان دوم",
            role="guest",
        )
        session.add_all([host, other, guest, other_guest])
        await session.flush()

        listing = Listing(
            host_id=host.id,
            title=LISTING_TITLE,
            city="یزد",
            address="بافت تاریخی یزد",
            status="published",
        )
        other_listing = Listing(
            host_id=other.id,
            title="اقامتگاه میزبان دیگر",
            city="کاشان",
            address="روستای ده‌زیر",
            status="published",
        )
        session.add_all([listing, other_listing])
        await session.flush()

        room = Room(
            listing_id=listing.id, name=ROOM_NAME, capacity=2, price_per_night=1450000
        )
        other_room = Room(
            listing_id=other_listing.id, name="اتاق دیگر", capacity=2, price_per_night=900000
        )
        session.add_all([room, other_room])
        await session.flush()

        pending = Booking(
            room_id=room.id,
            guest_id=guest.id,
            check_in=DAY,
            check_out=DAY + timedelta(days=3),
            status="pending",
        )
        other_pending = Booking(
            room_id=other_room.id,
            guest_id=other_guest.id,
            check_in=DAY,
            check_out=DAY + timedelta(days=2),
            status="pending",
        )
        session.add_all([pending, other_pending])
        await session.commit()

        ids["listing"] = listing.id
        ids["room"] = room.id
        ids["other_room"] = other_room.id
        ids["booking"] = pending.id
        ids["other_booking"] = other_pending.id

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


def _headers(token: str | None = None, key: str | None = None) -> dict[str, str]:
    headers: dict[str, str] = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if key:
        headers["Idempotency-Key"] = key
    return headers


# ------------------------------------------------------------------ host inbox


def test_host_bookings_requires_authentication():
    async def scenario():
        async with api_client() as (client, _ids):
            response = await client.get("/api/v1/bookings/host")
            assert response.status_code == 401, response.text

    asyncio.run(scenario())


def test_host_sees_only_bookings_for_own_listings():
    async def scenario():
        async with api_client() as (client, ids):
            token = await _login(client, HOST)
            response = await client.get(
                "/api/v1/bookings/host", headers=_headers(token)
            )
            assert response.status_code == 200, response.text
            rows = response.json()

            assert [row["id"] for row in rows] == [str(ids["booking"])]
            row = rows[0]
            assert row["guest_email"] == GUEST["email"]
            assert row["guest_name"] == "کاربر مهمان"
            assert row["room_name"] == ROOM_NAME
            assert row["listing_title"] == LISTING_TITLE
            assert row["status"] == "pending"

            other_token = await _login(client, OTHER_HOST)
            other = await client.get(
                "/api/v1/bookings/host", headers=_headers(other_token)
            )
            assert [row["id"] for row in other.json()] == [str(ids["other_booking"])]

    asyncio.run(scenario())


def test_host_confirms_a_pending_booking():
    async def scenario():
        async with api_client() as (client, ids):
            token = await _login(client, HOST)
            response = await client.patch(
                f"/api/v1/bookings/{ids['booking']}/confirm",
                headers=_headers(token, str(uuid.uuid4())),
            )
            assert response.status_code == 200, response.text
            assert response.json()["status"] == "confirmed"

            again = await client.patch(
                f"/api/v1/bookings/{ids['booking']}/confirm",
                headers=_headers(token, str(uuid.uuid4())),
            )
            assert again.status_code == 200, again.text
            assert again.json()["status"] == "confirmed"

    asyncio.run(scenario())


def test_confirm_requires_idempotency_key():
    async def scenario():
        async with api_client() as (client, ids):
            token = await _login(client, HOST)
            response = await client.patch(
                f"/api/v1/bookings/{ids['booking']}/confirm", headers=_headers(token)
            )
            assert response.status_code == 422, response.text

    asyncio.run(scenario())


def test_other_host_cannot_confirm_or_cancel():
    async def scenario():
        async with api_client() as (client, ids):
            token = await _login(client, OTHER_HOST)
            for action in ("confirm", "cancel"):
                response = await client.patch(
                    f"/api/v1/bookings/{ids['booking']}/{action}",
                    headers=_headers(token, str(uuid.uuid4())),
                )
                assert response.status_code == 403, response.text

    asyncio.run(scenario())


def test_confirm_unknown_booking_is_404():
    async def scenario():
        async with api_client() as (client, _ids):
            token = await _login(client, HOST)
            response = await client.patch(
                f"/api/v1/bookings/{uuid.uuid4()}/confirm",
                headers=_headers(token, str(uuid.uuid4())),
            )
            assert response.status_code == 404, response.text

    asyncio.run(scenario())


def test_cancelled_booking_cannot_be_confirmed():
    async def scenario():
        async with api_client() as (client, ids):
            token = await _login(client, HOST)
            cancel = await client.patch(
                f"/api/v1/bookings/{ids['booking']}/cancel",
                headers=_headers(token, str(uuid.uuid4())),
            )
            assert cancel.status_code == 200, cancel.text
            assert cancel.json()["status"] == "cancelled"

            confirm = await client.patch(
                f"/api/v1/bookings/{ids['booking']}/confirm",
                headers=_headers(token, str(uuid.uuid4())),
            )
            assert confirm.status_code == 409, confirm.text

    asyncio.run(scenario())


def test_cancelling_frees_the_dates_for_a_new_booking():
    async def scenario():
        async with api_client() as (client, ids):
            host_token = await _login(client, HOST)
            guest_token = await _login(client, GUEST)

            blocked = await client.post(
                "/api/v1/bookings",
                json={
                    "room_id": str(ids["room"]),
                    "check_in": str(DAY),
                    "check_out": str(DAY + timedelta(days=1)),
                },
                headers=_headers(guest_token, str(uuid.uuid4())),
            )
            assert blocked.status_code == 409, blocked.text

            cancel = await client.patch(
                f"/api/v1/bookings/{ids['booking']}/cancel",
                headers=_headers(host_token, str(uuid.uuid4())),
            )
            assert cancel.status_code == 200, cancel.text

            freed = await client.post(
                "/api/v1/bookings",
                json={
                    "room_id": str(ids["room"]),
                    "check_in": str(DAY),
                    "check_out": str(DAY + timedelta(days=1)),
                },
                headers=_headers(guest_token, str(uuid.uuid4())),
            )
            assert freed.status_code == 201, freed.text

    asyncio.run(scenario())


# ----------------------------------------------------------------- guest inbox


def test_my_bookings_requires_authentication():
    async def scenario():
        async with api_client() as (client, _ids):
            response = await client.get("/api/v1/bookings/mine")
            assert response.status_code == 401, response.text

    asyncio.run(scenario())


def test_guest_sees_only_their_own_bookings():
    async def scenario():
        async with api_client() as (client, ids):
            token = await _login(client, GUEST)
            response = await client.get(
                "/api/v1/bookings/mine", headers=_headers(token)
            )
            assert response.status_code == 200, response.text
            rows = response.json()

            assert [row["id"] for row in rows] == [str(ids["booking"])]
            row = rows[0]
            assert row["room_name"] == ROOM_NAME
            assert row["listing_title"] == LISTING_TITLE
            assert row["listing_city"] == "یزد"
            assert row["price_per_night"] == 1450000
            assert row["status"] == "pending"

            other_token = await _login(client, OTHER_GUEST)
            other = await client.get(
                "/api/v1/bookings/mine", headers=_headers(other_token)
            )
            assert [row["id"] for row in other.json()] == [str(ids["other_booking"])]

    asyncio.run(scenario())


# --------------------------------------------------------------------- pages


def test_host_bookings_page_renders():
    async def scenario():
        async with api_client() as (client, _ids):
            response = await client.get("/host/bookings")
            assert response.status_code == 200, response.text
            body = response.text
            assert 'id="host-bookings-body"' in body
            assert "/api/v1/bookings/host" in body
            assert "/confirm" in body and "/cancel" in body
            assert "تأیید" in body and "لغو" in body
            assert "http://" not in body and "https://" not in body

    asyncio.run(scenario())


def test_profile_bookings_page_renders():
    async def scenario():
        async with api_client() as (client, _ids):
            response = await client.get("/profile/bookings")
            assert response.status_code == 200, response.text
            body = response.text
            assert 'id="my-bookings-body"' in body
            assert "/api/v1/bookings/mine" in body
            assert "http://" not in body and "https://" not in body

    asyncio.run(scenario())


def test_host_page_links_to_the_bookings_inbox():
    async def scenario():
        async with api_client() as (client, _ids):
            response = await client.get("/host")
            assert response.status_code == 200, response.text
            assert 'href="/host/bookings"' in response.text

    asyncio.run(scenario())


def test_profile_page_links_to_the_guest_bookings():
    async def scenario():
        async with api_client() as (client, _ids):
            response = await client.get("/profile")
            assert response.status_code == 200, response.text
            assert 'href="/profile/bookings"' in response.text

    asyncio.run(scenario())


# -------------------------------------------------------------------- navbar


def test_homepage_navbar_switches_with_the_token():
    async def scenario():
        async with api_client() as (client, _ids):
            response = await client.get("/")
            assert response.status_code == 200, response.text
            body = response.text
            assert 'id="nav-login"' in body
            assert 'id="nav-profile"' in body
            assert 'id="nav-logout"' in body
            assert "پروفایل من" in body
            assert "localStorage.getItem" in body
            assert "removeItem" in body

    asyncio.run(scenario())


def test_admin_and_profile_pages_clear_the_token_on_logout():
    async def scenario():
        async with api_client() as (client, _ids):
            for path in ("/admin", "/profile"):
                response = await client.get(path)
                assert response.status_code == 200, response.text
                assert "localStorage.removeItem" in response.text, path
                assert "location.replace('/')" in response.text, path

    asyncio.run(scenario())


# ----------------------------------------------------------------- migration


def test_alembic_migration_declares_the_postgres_exclusion_constraint():
    versions = Path("alembic/versions")
    assert versions.is_dir(), "alembic/versions must exist"
    sources = "\n".join(path.read_text(encoding="utf-8") for path in versions.glob("*.py"))
    assert "EXCLUDE USING gist" in sources
    assert "btree_gist" in sources
    assert "daterange" in sources
    assert "no_overlapping_bookings" in sources
    assert "postgresql" in sources
