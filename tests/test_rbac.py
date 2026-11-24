"""Phase 7 acceptance tests: role-aware login and separate dashboards.

Written before the implementation (Iron Rule 1). Runs against an in-memory
SQLite database with ``get_db`` overridden, so ``dev.db`` is never touched.
"""

import asyncio
from contextlib import asynccontextmanager

from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
from app.core.security import hash_password
from app.main import app
from app.models.listing import Listing, Room
from app.models.user import User

ACCOUNTS = {
    "admin": {"email": "admin@boom.local", "password": "Admin@1234", "role": "admin"},
    "host": {"email": "host@boom.local", "password": "Host@1234", "role": "host"},
    "guest": {"email": "guest@boom.local", "password": "Guest@1234", "role": "guest"},
}


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
        users = {}
        for name, account in ACCOUNTS.items():
            users[name] = User(
                email=account["email"],
                password_hash=hash_password(account["password"]),
                full_name="میزبان بوم" if name == "host" else "کاربر",
                role=account["role"],
            )
        session.add_all(users.values())
        await session.flush()

        listing = Listing(
            host_id=users["host"].id,
            title="اقامتگاه منتشرشده کویر",
            city="یزد",
            address="بافت تاریخی یزد",
            status="published",
        )
        session.add(listing)
        await session.flush()
        session.add(
            Room(listing_id=listing.id, name="اتاق نخل", capacity=2, price_per_night=1450000)
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


def test_login_response_carries_the_role_for_every_account():
    async def scenario():
        async with api_client() as client:
            for name, account in ACCOUNTS.items():
                response = await client.post(
                    "/api/v1/auth/login",
                    json={"email": account["email"], "password": account["password"]},
                )
                assert response.status_code == 200, response.text
                body = response.json()

                assert body["role"] == account["role"], name
                assert body["token_type"] == "bearer"
                assert body["access_token"].count(".") == 2
                # The nested user object is still there for the existing pages.
                assert body["user"]["role"] == account["role"]
                assert "password" not in body["user"]

    asyncio.run(scenario())


def test_login_page_sends_each_role_to_its_dashboard():
    async def scenario():
        async with api_client() as client:
            response = await client.get("/login")
            assert response.status_code == 200, response.text
            body = response.text

            assert "ROLE_HOME" in body
            assert "admin: '/admin'" in body
            assert "host: '/host'" in body
            assert "guest: '/profile'" in body
            # The role now comes from the response body first.
            assert "payload.role" in body

    asyncio.run(scenario())


def test_host_dashboard_shows_incoming_bookings():
    async def scenario():
        async with api_client() as client:
            response = await client.get("/host")
            assert response.status_code == 200, response.text
            body = response.text

            assert 'id="host-recent-bookings"' in body
            assert "/api/v1/bookings/host" in body
            assert "رزروهای اخیر" in body
            assert 'href="/host/bookings"' in body
            # The listings console is still there.
            assert 'id="my-listings-body"' in body
            assert 'id="room-form"' in body

    asyncio.run(scenario())


def test_profile_page_labels_hosts_correctly_and_lists_bookings():
    async def scenario():
        async with api_client() as client:
            response = await client.get("/profile")
            assert response.status_code == 200, response.text
            body = response.text

            # Role labels come from a map, so a host is no longer shown as guest.
            assert "ROLE_LABELS" in body
            assert "host: 'میزبان'" in body
            assert "user.role === 'admin' ? 'مدیر سامانه' : 'کاربر مهمان'" not in body

            # Bookings section for the signed-in user.
            assert 'id="profile-bookings"' in body
            assert 'id="profile-bookings-body"' in body
            assert "/api/v1/bookings/mine" in body
            assert "رزروهای من" in body

    asyncio.run(scenario())
