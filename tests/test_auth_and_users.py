"""Authentication and protected user-listing behaviour.

Run against an in-memory SQLite database with ``get_db`` overridden, so the
developer's ``dev.db`` is never touched.
"""

import asyncio
from contextlib import asynccontextmanager

from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
from app.core.security import hash_password
from app.main import app
from app.models.user import User

ADMIN = {"email": "admin@boom.local", "password": "Admin@1234", "role": "admin"}
GUEST = {"email": "guest@boom.local", "password": "Guest@1234", "role": "guest"}


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
        session.add_all(
            [
                User(
                    email=ADMIN["email"],
                    password_hash=hash_password(ADMIN["password"]),
                    full_name="مدیر سامانه",
                    role=ADMIN["role"],
                ),
                User(
                    email=GUEST["email"],
                    password_hash=hash_password(GUEST["password"]),
                    full_name="کاربر مهمان",
                    role=GUEST["role"],
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


async def _login(client: AsyncClient, credentials: dict) -> dict:
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": credentials["email"], "password": credentials["password"]},
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_login_returns_real_jwt():
    async def scenario():
        async with api_client() as client:
            body = await _login(client, ADMIN)
            assert body["token_type"] == "bearer"
            assert body["access_token"].count(".") == 2
            assert body["user"]["role"] == "admin"
            assert body["user"]["email"] == ADMIN["email"]
            assert "password" not in body["user"]

    asyncio.run(scenario())


def test_login_rejects_wrong_password():
    async def scenario():
        async with api_client() as client:
            response = await client.post(
                "/api/v1/auth/login",
                json={"email": ADMIN["email"], "password": "not-the-password"},
            )
            assert response.status_code == 401
            assert "access_token" not in response.text

    asyncio.run(scenario())


def test_login_rejects_unknown_email_with_same_detail():
    async def scenario():
        async with api_client() as client:
            wrong_email = await client.post(
                "/api/v1/auth/login",
                json={"email": "nobody@boom.local", "password": "whatever-1234"},
            )
            wrong_password = await client.post(
                "/api/v1/auth/login",
                json={"email": ADMIN["email"], "password": "whatever-1234"},
            )
            assert wrong_email.status_code == wrong_password.status_code == 401
            assert wrong_email.json() == wrong_password.json()

    asyncio.run(scenario())


def test_users_endpoint_requires_token():
    async def scenario():
        async with api_client() as client:
            response = await client.get("/api/v1/users/")
            assert response.status_code == 401

    asyncio.run(scenario())


def test_admin_can_list_users():
    async def scenario():
        async with api_client() as client:
            token = (await _login(client, ADMIN))["access_token"]
            response = await client.get(
                "/api/v1/users/", headers={"Authorization": f"Bearer {token}"}
            )
            assert response.status_code == 200
            emails = {row["email"] for row in response.json()}
            assert emails == {ADMIN["email"], GUEST["email"]}

    asyncio.run(scenario())


def test_guest_cannot_list_users():
    async def scenario():
        async with api_client() as client:
            token = (await _login(client, GUEST))["access_token"]
            response = await client.get(
                "/api/v1/users/", headers={"Authorization": f"Bearer {token}"}
            )
            assert response.status_code == 403

    asyncio.run(scenario())


def test_tampered_token_is_rejected():
    async def scenario():
        async with api_client() as client:
            token = (await _login(client, ADMIN))["access_token"]
            response = await client.get(
                "/api/v1/users/", headers={"Authorization": f"Bearer {token}x"}
            )
            assert response.status_code == 401

    asyncio.run(scenario())
