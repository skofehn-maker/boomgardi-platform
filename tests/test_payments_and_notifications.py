"""Phase 14 acceptance tests: mock payment page + in-app notifications.

Written before the implementation (Iron Rule 1). In-memory SQLite only; the
notification rows are asserted through the API, never against ``dev.db``.
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
from app.models.notification import Notification
from app.models.user import User

HOST = {"email": "host@boom.local", "password": "Host@1234"}
GUEST = {"email": "guest@boom.local", "password": "Guest@1234"}


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

    ids = {}
    async with session_factory() as session:
        host = User(
            email=HOST["email"],
            password_hash=hash_password(HOST["password"]),
            full_name="میزبان باغ",
            role="host",
        )
        guest = User(
            email=GUEST["email"],
            password_hash=hash_password(GUEST["password"]),
            full_name="مهمان باغ",
            role="guest",
        )
        session.add_all([host, guest])
        await session.flush()

        listing = Listing(
            host_id=host.id,
            title="اقامتگاه باغ ایرانی",
            city="یزد",
            address="یزد",
            status="published",
        )
        session.add(listing)
        await session.flush()

        room = Room(
            listing_id=listing.id,
            name="اتاق گل",
            capacity=2,
            price_per_night=900000,
        )
        session.add(room)
        await session.flush()

        today = date.today()
        booking = Booking(
            room_id=room.id,
            guest_id=guest.id,
            check_in=today + timedelta(days=7),
            check_out=today + timedelta(days=10),
            status="pending",
        )
        session.add(booking)
        await session.commit()

        ids = {
            "booking": booking.id,
            "guest": guest.id,
            "host": host.id,
            "listing": listing.id,
        }

    async def override_get_db():
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://testserver"
        ) as client:
            client.ids = ids
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


def _headers(token: str, key: str | None = None) -> dict[str, str]:
    headers = {"Authorization": f"Bearer {token}"}
    if key:
        headers["Idempotency-Key"] = key
    return headers


def test_notification_model_shape():
    columns = Notification.__table__.columns
    assert {"id", "user_id", "message", "is_read", "created_at"} <= set(columns.keys())
    assert columns["is_read"].default.arg is False
    assert "user_id" in {column.name for column in Notification.__table__.columns}
    index_columns = {
        tuple(sorted(column.name for column in index.columns))
        for index in Notification.__table__.indexes
    }
    assert ("is_read", "user_id") in index_columns or ("user_id", "is_read") in index_columns


def test_notification_endpoints_require_authentication():
    async def scenario():
        async with seeded_client() as client:
            for path in ("/api/v1/notifications/unread", "/api/v1/notifications"):
                response = await client.get(path)
                assert response.status_code == 401, (path, response.text)

            mark = await client.patch(
                "/api/v1/notifications/read",
                headers={"Idempotency-Key": str(uuid.uuid4())},
            )
            assert mark.status_code == 401, mark.text

    asyncio.run(scenario())


def test_paying_creates_one_unread_notification_for_the_guest():
    async def scenario():
        async with seeded_client() as client:
            token = await _token(client, GUEST)
            booking_id = client.ids["booking"]

            pay = await client.patch(
                f"/api/v1/bookings/{booking_id}/pay",
                headers=_headers(token, str(uuid.uuid4())),
            )
            assert pay.status_code == 200, pay.text
            assert pay.json()["status"] == "confirmed"

            unread = await client.get(
                "/api/v1/notifications/unread", headers=_headers(token)
            )
            assert unread.status_code == 200, unread.text
            rows = unread.json()
            assert len(rows) == 1
            assert "تأیید" in rows[0]["message"]
            assert rows[0]["is_read"] is False

            # Replaying the same action does not stack a second notice.
            again = await client.patch(
                f"/api/v1/bookings/{booking_id}/pay",
                headers=_headers(token, str(uuid.uuid4())),
            )
            assert again.status_code == 200, again.text
            unread_again = await client.get(
                "/api/v1/notifications/unread", headers=_headers(token)
            )
            assert len(unread_again.json()) == 1

    asyncio.run(scenario())


def test_confirming_notifies_the_guest_and_cancelling_notifies_the_host():
    async def scenario():
        async with seeded_client() as client:
            host_token = await _token(client, HOST)
            guest_token = await _token(client, GUEST)
            booking_id = client.ids["booking"]

            confirm = await client.patch(
                f"/api/v1/bookings/{booking_id}/confirm",
                headers=_headers(host_token, str(uuid.uuid4())),
            )
            assert confirm.status_code == 200, confirm.text

            guest_unread = await client.get(
                "/api/v1/notifications/unread", headers=_headers(guest_token)
            )
            assert len(guest_unread.json()) == 1
            assert "تأیید" in guest_unread.json()[0]["message"]

            cancel = await client.patch(
                f"/api/v1/bookings/{booking_id}/cancel",
                headers=_headers(guest_token, str(uuid.uuid4())),
            )
            assert cancel.status_code == 200, cancel.text

            host_unread = await client.get(
                "/api/v1/notifications/unread", headers=_headers(host_token)
            )
            assert host_unread.status_code == 200, host_unread.text
            assert len(host_unread.json()) == 1
            assert "لغو" in host_unread.json()[0]["message"]

    asyncio.run(scenario())


def test_notifications_are_never_shared_between_accounts():
    async def scenario():
        async with seeded_client() as client:
            guest_token = await _token(client, GUEST)
            host_token = await _token(client, HOST)
            booking_id = client.ids["booking"]

            await client.patch(
                f"/api/v1/bookings/{booking_id}/pay",
                headers=_headers(guest_token, str(uuid.uuid4())),
            )

            host_rows = await client.get(
                "/api/v1/notifications", headers=_headers(host_token)
            )
            assert host_rows.json() == []

            guest_rows = await client.get(
                "/api/v1/notifications", headers=_headers(guest_token)
            )
            assert len(guest_rows.json()) == 1

    asyncio.run(scenario())


def test_marking_read_is_scoped_idempotent_and_counts_rows():
    async def scenario():
        async with seeded_client() as client:
            guest_token = await _token(client, GUEST)
            host_token = await _token(client, HOST)
            booking_id = client.ids["booking"]

            await client.patch(
                f"/api/v1/bookings/{booking_id}/pay",
                headers=_headers(guest_token, str(uuid.uuid4())),
            )

            missing_key = await client.patch(
                "/api/v1/notifications/read", headers=_headers(guest_token)
            )
            assert missing_key.status_code == 422, missing_key.text

            marked = await client.patch(
                "/api/v1/notifications/read",
                headers=_headers(guest_token, str(uuid.uuid4())),
            )
            assert marked.status_code == 200, marked.text
            assert marked.json()["updated"] == 1

            unread = await client.get(
                "/api/v1/notifications/unread", headers=_headers(guest_token)
            )
            assert unread.json() == []

            latest = await client.get(
                "/api/v1/notifications", headers=_headers(guest_token)
            )
            assert len(latest.json()) == 1
            assert latest.json()[0]["is_read"] is True

            replay = await client.patch(
                "/api/v1/notifications/read",
                headers=_headers(guest_token, str(uuid.uuid4())),
            )
            assert replay.json()["updated"] == 0

            # The host's rows were never touched (they have none here).
            host_replay = await client.patch(
                "/api/v1/notifications/read",
                headers=_headers(host_token, str(uuid.uuid4())),
            )
            assert host_replay.json()["updated"] == 0

    asyncio.run(scenario())


def test_latest_notifications_honour_the_limit():
    async def scenario():
        async with seeded_client() as client:
            guest_token = await _token(client, GUEST)
            booking_id = client.ids["booking"]

            await client.patch(
                f"/api/v1/bookings/{booking_id}/pay",
                headers=_headers(guest_token, str(uuid.uuid4())),
            )

            limited = await client.get(
                "/api/v1/notifications?limit=1", headers=_headers(guest_token)
            )
            assert len(limited.json()) == 1

            invalid = await client.get(
                "/api/v1/notifications?limit=0", headers=_headers(guest_token)
            )
            assert invalid.status_code == 422, invalid.text

    asyncio.run(scenario())


def test_payment_page_is_served_and_shows_the_pay_button():
    async def scenario():
        async with seeded_client() as client:
            response = await client.get(f"/payment/{client.ids['booking']}")
            assert response.status_code == 200, response.text
            body = response.text

            assert "پرداخت آنلاین" in body
            assert "/api/v1/bookings/" in body
            assert "Idempotency-Key" in body
            assert "Coffee" not in body  # no stray placeholder copy

    asyncio.run(scenario())


def test_profile_links_to_the_payment_page_instead_of_paying_directly():
    async def scenario():
        async with seeded_client() as client:
            body = (await client.get("/profile")).text
            assert "/payment/" in body
            assert "data-action', 'pay'" not in body
            assert "notifications.js" in body
            assert 'id="notification-bell"' in body

    asyncio.run(scenario())


def test_homepage_mounts_the_notification_bell():
    async def scenario():
        async with seeded_client() as client:
            body = (await client.get("/")).text
            assert 'id="notification-bell"' in body
            assert "notifications.js" in body
            assert "notifications.css" in body

    asyncio.run(scenario())
