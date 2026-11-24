"""Phase 5 acceptance tests: rooms on a listing and guest bookings.

Written before the implementation (Iron Rule 1). Runs against an in-memory
SQLite database with ``get_db`` overridden, so ``dev.db`` is never touched.
"""

import asyncio
import uuid
from contextlib import asynccontextmanager
from datetime import date, timedelta

from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select
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

ROOM = {"name": "اتاق گل‌سرخ", "capacity": 2, "price_per_night": 1450000.0}

# Well clear of "today" in any timezone, and stable across a test run.
DAY = date.today() + timedelta(days=10)


@asynccontextmanager
async def api_client():
    """Yield ``(client, session_factory, ids)`` on a fresh in-memory database."""
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
        session.add_all([host, other, guest])
        await session.flush()

        published = Listing(
            host_id=host.id,
            title="اقامتگاه منتشرشده کویر",
            city="یزد",
            address="بافت تاریخی یزد",
            status="published",
        )
        draft = Listing(
            host_id=host.id,
            title="اقامتگاه پیش‌نویس کوهسار",
            city="کاشان",
            address="روستای ده‌زیر",
            status="draft",
        )
        session.add_all([published, draft])
        await session.flush()

        room = Room(
            listing_id=published.id,
            name=ROOM["name"],
            capacity=ROOM["capacity"],
            price_per_night=ROOM["price_per_night"],
        )
        draft_room = Room(
            listing_id=draft.id, name="اتاق پیش‌نویس", capacity=2, price_per_night=900000
        )
        session.add_all([room, draft_room])
        await session.commit()

        ids["published"] = published.id
        ids["draft"] = draft.id
        ids["room"] = room.id
        ids["draft_room"] = draft_room.id

    async def override_get_db():
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://testserver"
        ) as client:
            yield client, session_factory, ids
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


# --------------------------------------------------------------------------- rooms


def test_add_room_requires_authentication():
    async def scenario():
        async with api_client() as (client, _factory, ids):
            response = await client.post(
                f"/api/v1/listings/{ids['published']}/rooms",
                json=ROOM,
                headers=_headers(key=str(uuid.uuid4())),
            )
            assert response.status_code == 401, response.text

    asyncio.run(scenario())


def test_add_room_requires_idempotency_key():
    async def scenario():
        async with api_client() as (client, _factory, ids):
            token = await _login(client, HOST)
            response = await client.post(
                f"/api/v1/listings/{ids['published']}/rooms",
                json=ROOM,
                headers=_headers(token),
            )
            assert response.status_code == 422, response.text

    asyncio.run(scenario())


def test_host_adds_room_to_own_listing():
    async def scenario():
        async with api_client() as (client, _factory, ids):
            token = await _login(client, HOST)
            response = await client.post(
                f"/api/v1/listings/{ids['published']}/rooms",
                json=ROOM,
                headers=_headers(token, str(uuid.uuid4())),
            )
            assert response.status_code == 201, response.text
            body = response.json()
            assert body["name"] == ROOM["name"]
            assert body["capacity"] == ROOM["capacity"]
            assert body["price_per_night"] == ROOM["price_per_night"]
            assert body["listing_id"] == str(ids["published"])

    asyncio.run(scenario())


def test_add_room_replay_returns_the_same_room():
    async def scenario():
        async with api_client() as (client, factory, ids):
            token = await _login(client, HOST)
            key = str(uuid.uuid4())
            url = f"/api/v1/listings/{ids['published']}/rooms"

            first = await client.post(url, json=ROOM, headers=_headers(token, key))
            second = await client.post(url, json=ROOM, headers=_headers(token, key))

            assert first.status_code == 201, first.text
            assert second.status_code == 201, second.text
            assert first.json()["id"] == second.json()["id"]

            async with factory() as session:
                total = await session.scalar(
                    select(func.count()).select_from(Room).where(
                        Room.listing_id == ids["published"]
                    )
                )
            assert total == 2  # the seeded room plus exactly one new one

    asyncio.run(scenario())


def test_other_host_cannot_add_room():
    async def scenario():
        async with api_client() as (client, _factory, ids):
            token = await _login(client, OTHER_HOST)
            response = await client.post(
                f"/api/v1/listings/{ids['published']}/rooms",
                json=ROOM,
                headers=_headers(token, str(uuid.uuid4())),
            )
            assert response.status_code == 403, response.text

    asyncio.run(scenario())


def test_add_room_to_unknown_listing_is_404():
    async def scenario():
        async with api_client() as (client, _factory, _ids):
            token = await _login(client, HOST)
            response = await client.post(
                f"/api/v1/listings/{uuid.uuid4()}/rooms",
                json=ROOM,
                headers=_headers(token, str(uuid.uuid4())),
            )
            assert response.status_code == 404, response.text

    asyncio.run(scenario())


def test_room_validation_rejects_zero_capacity():
    async def scenario():
        async with api_client() as (client, _factory, ids):
            token = await _login(client, HOST)
            response = await client.post(
                f"/api/v1/listings/{ids['published']}/rooms",
                json={**ROOM, "capacity": 0},
                headers=_headers(token, str(uuid.uuid4())),
            )
            assert response.status_code == 422, response.text

    asyncio.run(scenario())


# ------------------------------------------------------------------ public detail


def test_public_detail_returns_published_listing_with_rooms():
    async def scenario():
        async with api_client() as (client, _factory, ids):
            response = await client.get(f"/api/v1/listings/{ids['published']}")
            assert response.status_code == 200, response.text
            body = response.json()
            assert body["id"] == str(ids["published"])
            assert [room["name"] for room in body["rooms"]] == [ROOM["name"]]

    asyncio.run(scenario())


def test_public_detail_hides_drafts():
    async def scenario():
        async with api_client() as (client, _factory, ids):
            response = await client.get(f"/api/v1/listings/{ids['draft']}")
            assert response.status_code == 404, response.text

    asyncio.run(scenario())


# ---------------------------------------------------------------------- bookings


def test_booking_requires_authentication():
    async def scenario():
        async with api_client() as (client, _factory, ids):
            response = await client.post(
                "/api/v1/bookings",
                json={
                    "room_id": str(ids["room"]),
                    "check_in": str(DAY),
                    "check_out": str(DAY + timedelta(days=2)),
                },
                headers=_headers(key=str(uuid.uuid4())),
            )
            assert response.status_code == 401, response.text

    asyncio.run(scenario())


def test_booking_requires_idempotency_key():
    async def scenario():
        async with api_client() as (client, _factory, ids):
            token = await _login(client, GUEST)
            response = await client.post(
                "/api/v1/bookings",
                json={
                    "room_id": str(ids["room"]),
                    "check_in": str(DAY),
                    "check_out": str(DAY + timedelta(days=2)),
                },
                headers=_headers(token),
            )
            assert response.status_code == 422, response.text

    asyncio.run(scenario())


def test_guest_books_a_room():
    async def scenario():
        async with api_client() as (client, factory, ids):
            token = await _login(client, GUEST)
            response = await client.post(
                "/api/v1/bookings",
                json={
                    "room_id": str(ids["room"]),
                    "check_in": str(DAY),
                    "check_out": str(DAY + timedelta(days=2)),
                },
                headers=_headers(token, str(uuid.uuid4())),
            )
            assert response.status_code == 201, response.text
            body = response.json()
            assert body["room_id"] == str(ids["room"])
            assert body["status"] == "pending"
            assert body["check_in"] == str(DAY)
            assert body["check_out"] == str(DAY + timedelta(days=2))
            assert "guest_id" in body and "created_at" in body

            async with factory() as session:
                stored = await session.scalar(select(func.count()).select_from(Booking))
            assert stored == 1

    asyncio.run(scenario())


def test_booking_rejects_inverted_dates():
    async def scenario():
        async with api_client() as (client, _factory, ids):
            token = await _login(client, GUEST)
            response = await client.post(
                "/api/v1/bookings",
                json={
                    "room_id": str(ids["room"]),
                    "check_in": str(DAY + timedelta(days=2)),
                    "check_out": str(DAY),
                },
                headers=_headers(token, str(uuid.uuid4())),
            )
            assert response.status_code == 422, response.text

    asyncio.run(scenario())


def test_booking_rejects_past_check_in():
    async def scenario():
        async with api_client() as (client, _factory, ids):
            token = await _login(client, GUEST)
            past = date.today() - timedelta(days=3)
            response = await client.post(
                "/api/v1/bookings",
                json={
                    "room_id": str(ids["room"]),
                    "check_in": str(past),
                    "check_out": str(past + timedelta(days=2)),
                },
                headers=_headers(token, str(uuid.uuid4())),
            )
            assert response.status_code == 422, response.text

    asyncio.run(scenario())


def test_overlapping_booking_is_refused():
    async def scenario():
        async with api_client() as (client, _factory, ids):
            token = await _login(client, GUEST)
            first = await client.post(
                "/api/v1/bookings",
                json={
                    "room_id": str(ids["room"]),
                    "check_in": str(DAY),
                    "check_out": str(DAY + timedelta(days=3)),
                },
                headers=_headers(token, str(uuid.uuid4())),
            )
            assert first.status_code == 201, first.text

            overlapping = await client.post(
                "/api/v1/bookings",
                json={
                    "room_id": str(ids["room"]),
                    "check_in": str(DAY + timedelta(days=1)),
                    "check_out": str(DAY + timedelta(days=2)),
                },
                headers=_headers(token, str(uuid.uuid4())),
            )
            assert overlapping.status_code == 409, overlapping.text

    asyncio.run(scenario())


def test_adjacent_stay_is_allowed():
    async def scenario():
        async with api_client() as (client, _factory, ids):
            token = await _login(client, GUEST)
            first = await client.post(
                "/api/v1/bookings",
                json={
                    "room_id": str(ids["room"]),
                    "check_in": str(DAY),
                    "check_out": str(DAY + timedelta(days=2)),
                },
                headers=_headers(token, str(uuid.uuid4())),
            )
            assert first.status_code == 201, first.text

            adjacent = await client.post(
                "/api/v1/bookings",
                json={
                    "room_id": str(ids["room"]),
                    "check_in": str(DAY + timedelta(days=2)),
                    "check_out": str(DAY + timedelta(days=4)),
                },
                headers=_headers(token, str(uuid.uuid4())),
            )
            assert adjacent.status_code == 201, adjacent.text

    asyncio.run(scenario())


def test_booking_replay_returns_the_same_booking():
    async def scenario():
        async with api_client() as (client, factory, ids):
            token = await _login(client, GUEST)
            key = str(uuid.uuid4())
            payload = {
                "room_id": str(ids["room"]),
                "check_in": str(DAY),
                "check_out": str(DAY + timedelta(days=2)),
            }

            first = await client.post(
                "/api/v1/bookings", json=payload, headers=_headers(token, key)
            )
            second = await client.post(
                "/api/v1/bookings", json=payload, headers=_headers(token, key)
            )

            assert first.status_code == 201, first.text
            assert second.status_code == 201, second.text
            assert first.json()["id"] == second.json()["id"]

            async with factory() as session:
                stored = await session.scalar(select(func.count()).select_from(Booking))
            assert stored == 1

    asyncio.run(scenario())


def test_cannot_book_a_room_in_an_unpublished_listing():
    async def scenario():
        async with api_client() as (client, _factory, ids):
            token = await _login(client, GUEST)
            response = await client.post(
                "/api/v1/bookings",
                json={
                    "room_id": str(ids["draft_room"]),
                    "check_in": str(DAY),
                    "check_out": str(DAY + timedelta(days=2)),
                },
                headers=_headers(token, str(uuid.uuid4())),
            )
            assert response.status_code == 404, response.text

    asyncio.run(scenario())


def test_unknown_room_is_404():
    async def scenario():
        async with api_client() as (client, _factory, _ids):
            token = await _login(client, GUEST)
            response = await client.post(
                "/api/v1/bookings",
                json={
                    "room_id": str(uuid.uuid4()),
                    "check_in": str(DAY),
                    "check_out": str(DAY + timedelta(days=2)),
                },
                headers=_headers(token, str(uuid.uuid4())),
            )
            assert response.status_code == 404, response.text

    asyncio.run(scenario())


# --------------------------------------------------------------------- templates


def test_listing_detail_page_renders():
    async def scenario():
        async with api_client() as (client, _factory, ids):
            response = await client.get(f"/listings/{ids['published']}")
            assert response.status_code == 200, response.text
            body = response.text
            assert 'id="booking-form"' in body
            assert 'id="room-select"' in body
            assert 'id="check-in"' in body
            assert 'id="check-out"' in body
            assert "ثبت رزرو" in body
            assert "#f5f0e6" in body
            assert "http://" not in body and "https://" not in body

    asyncio.run(scenario())


def test_homepage_cards_link_to_the_detail_page():
    async def scenario():
        async with api_client() as (client, _factory, _ids):
            response = await client.get("/")
            assert response.status_code == 200, response.text
            body = response.text
            assert "مشاهده و رزرو" in body
            assert "/listings/" in body
            assert "نشو" not in body

    asyncio.run(scenario())


def test_host_page_offers_the_add_room_action():
    async def scenario():
        async with api_client() as (client, _factory, _ids):
            response = await client.get("/host")
            assert response.status_code == 200, response.text
            body = response.text
            assert "افزودن اتاق" in body
            assert 'id="room-form"' in body
            assert 'id="room-listing-id"' in body

    asyncio.run(scenario())
