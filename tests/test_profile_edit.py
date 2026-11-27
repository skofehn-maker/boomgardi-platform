"""Phase 12 acceptance tests: self-service profile editing.

Written before the implementation (Iron Rule 1). Runs against an in-memory
SQLite database with ``get_db`` overridden, so ``dev.db`` is never touched.
"""

import asyncio
import uuid
from contextlib import asynccontextmanager

from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
from app.core.security import hash_password
from app.main import app
from app.models.user import User

GUEST = {"email": "guest@boom.local", "password": "Guest@1234"}
OTHER = {"email": "other@boom.local", "password": "Other@1234"}


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
                    email=GUEST["email"],
                    password_hash=hash_password(GUEST["password"]),
                    full_name="کاربر مهمان",
                    role="guest",
                ),
                User(
                    email=OTHER["email"],
                    password_hash=hash_password(OTHER["password"]),
                    full_name="کاربر دیگر",
                    role="guest",
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


async def _login(client: AsyncClient, credentials: dict):
    return await client.post(
        "/api/v1/auth/login",
        json={"email": credentials["email"], "password": credentials["password"]},
    )


async def _token(client: AsyncClient) -> str:
    response = await _login(client, GUEST)
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def _headers(token: str, key: str | None = None) -> dict[str, str]:
    headers = {"Authorization": f"Bearer {token}"}
    if key:
        headers["Idempotency-Key"] = key
    return headers


def test_update_profile_requires_authentication():
    async def scenario():
        async with api_client() as client:
            response = await client.put(
                "/api/v1/users/me",
                json={"full_name": "نام تازه"},
                headers={"Idempotency-Key": str(uuid.uuid4())},
            )
            assert response.status_code == 401, response.text

    asyncio.run(scenario())


def test_update_profile_requires_an_idempotency_key():
    async def scenario():
        async with api_client() as client:
            token = await _token(client)
            response = await client.put(
                "/api/v1/users/me",
                json={"full_name": "نام تازه"},
                headers=_headers(token),
            )
            assert response.status_code == 422, response.text

    asyncio.run(scenario())


def test_guest_can_rename_themselves():
    async def scenario():
        async with api_client() as client:
            token = await _token(client)
            response = await client.put(
                "/api/v1/users/me",
                json={"full_name": "   سارا احمدی  "},
                headers=_headers(token, str(uuid.uuid4())),
            )
            assert response.status_code == 200, response.text
            assert response.json()["full_name"] == "سارا احمدی"
            assert response.json()["email"] == GUEST["email"]

            # The change is persisted: login reports the new name.
            again = await _login(client, GUEST)
            assert again.json()["user"]["full_name"] == "سارا احمدی"

    asyncio.run(scenario())


def test_password_change_replaces_the_old_password():
    async def scenario():
        async with api_client() as client:
            token = await _token(client)
            response = await client.put(
                "/api/v1/users/me",
                json={"password": "NewPass@2026"},
                headers=_headers(token, str(uuid.uuid4())),
            )
            assert response.status_code == 200, response.text

            old = await _login(client, GUEST)
            assert old.status_code != 200, old.text

            new = await client.post(
                "/api/v1/auth/login",
                json={"email": GUEST["email"], "password": "NewPass@2026"},
            )
            assert new.status_code == 200, new.text

    asyncio.run(scenario())


def test_profile_update_never_touches_another_account():
    async def scenario():
        async with api_client() as client:
            other = await _login(client, OTHER)
            assert other.status_code == 200, other.text

            token = await _token(client)
            await client.put(
                "/api/v1/users/me",
                json={"full_name": "فقط من"},
                headers=_headers(token, str(uuid.uuid4())),
            )

            untouched = await client.post(
                "/api/v1/auth/login",
                json={"email": OTHER["email"], "password": OTHER["password"]},
            )
            assert untouched.json()["user"]["full_name"] == "کاربر دیگر"

    asyncio.run(scenario())


def test_short_password_and_empty_payload_are_rejected():
    async def scenario():
        async with api_client() as client:
            token = await _token(client)

            short = await client.put(
                "/api/v1/users/me",
                json={"password": "1234567"},
                headers=_headers(token, str(uuid.uuid4())),
            )
            assert short.status_code == 422, short.text

            empty = await client.put(
                "/api/v1/users/me",
                json={},
                headers=_headers(token, str(uuid.uuid4())),
            )
            assert empty.status_code == 422, empty.text

    asyncio.run(scenario())


def test_profile_page_renders_the_edit_form():
    async def scenario():
        async with api_client() as client:
            response = await client.get("/profile")
            assert response.status_code == 200, response.text
            body = response.text

            assert "ویرایش پروفایل" in body
            assert "ذخیره تغییرات" in body
            assert "/api/v1/users/me" in body
            assert "Idempotency-Key" in body
            assert "http://" not in body and "https://" not in body

    asyncio.run(scenario())
