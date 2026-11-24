"""Phase 2 acceptance tests for listings.

Written before the implementation (Iron Rule 1). Run against an in-memory SQLite
database with ``get_db`` overridden, so ``dev.db`` is never touched.
"""

import asyncio
import uuid
from contextlib import asynccontextmanager

from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
from app.core.security import hash_password
from app.main import app
from app.models.listing import Listing
from app.models.user import User

HOST = {"email": "host@boom.local", "password": "Host@1234", "full_name": "میزبان بوم"}
GUEST = {"email": "guest@boom.local", "password": "Guest@1234", "full_name": "کاربر مهمان"}

LISTING_PAYLOAD = {
    "title": "اقامتگاه بومگردی کوهسار",
    "description": "خانه‌ای خشتی در دامنه کوه با صبحانه محلی",
    "city": "کاشان",
    "address": "جاده قمصر، روستای ده‌زیر",
}


@asynccontextmanager
async def api_client():
    """Yield ``(client, session_factory)`` backed by a fresh in-memory database."""
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
                    email=HOST["email"],
                    password_hash=hash_password(HOST["password"]),
                    full_name=HOST["full_name"],
                    role="guest",
                ),
                User(
                    email=GUEST["email"],
                    password_hash=hash_password(GUEST["password"]),
                    full_name=GUEST["full_name"],
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
            yield client, session_factory
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


def _auth(token: str, idempotency_key: str | None = None) -> dict[str, str]:
    headers = {"Authorization": f"Bearer {token}"}
    if idempotency_key:
        headers["Idempotency-Key"] = idempotency_key
    return headers


def test_create_listing_requires_authentication():
    async def scenario():
        async with api_client() as (client, _factory):
            response = await client.post(
                "/api/v1/listings",
                json=LISTING_PAYLOAD,
                headers={"Idempotency-Key": str(uuid.uuid4())},
            )
            assert response.status_code == 401, response.text

    asyncio.run(scenario())


def test_create_listing_requires_idempotency_key():
    async def scenario():
        async with api_client() as (client, _factory):
            token = (await _login(client, HOST))["access_token"]
            response = await client.post(
                "/api/v1/listings", json=LISTING_PAYLOAD, headers=_auth(token)
            )
            assert response.status_code == 422, response.text

    asyncio.run(scenario())


def test_host_creates_draft_listing():
    async def scenario():
        async with api_client() as (client, _factory):
            login = await _login(client, HOST)
            response = await client.post(
                "/api/v1/listings",
                json=LISTING_PAYLOAD,
                headers=_auth(login["access_token"], str(uuid.uuid4())),
            )
            assert response.status_code == 201, response.text
            body = response.json()
            assert body["title"] == LISTING_PAYLOAD["title"]
            assert body["city"] == LISTING_PAYLOAD["city"]
            assert body["status"] == "draft"
            assert body["host_id"] == login["user"]["id"]
            assert body["rooms"] == []
            assert "created_at" in body

    asyncio.run(scenario())


def test_repeated_idempotency_key_returns_the_same_listing():
    async def scenario():
        async with api_client() as (client, factory):
            token = (await _login(client, HOST))["access_token"]
            key = str(uuid.uuid4())

            first = await client.post(
                "/api/v1/listings",
                json=LISTING_PAYLOAD,
                headers=_auth(token, key),
            )
            second = await client.post(
                "/api/v1/listings",
                json=LISTING_PAYLOAD,
                headers=_auth(token, key),
            )

            assert first.status_code == 201, first.text
            assert second.status_code == 201, second.text
            assert first.json()["id"] == second.json()["id"]

            async with factory() as session:
                total = await session.scalar(select(func.count()).select_from(Listing))
            assert total == 1

    asyncio.run(scenario())


def test_public_list_returns_only_published_listings():
    async def scenario():
        async with api_client() as (client, factory):
            login = await _login(client, HOST)
            host_id = uuid.UUID(login["user"]["id"])

            draft = await client.post(
                "/api/v1/listings",
                json=LISTING_PAYLOAD,
                headers=_auth(login["access_token"], str(uuid.uuid4())),
            )
            assert draft.status_code == 201, draft.text

            async with factory() as session:
                session.add(
                    Listing(
                        host_id=host_id,
                        title="اقامتگاه منتشرشده",
                        description="نمونه منتشرشده",
                        city="یزد",
                        address="بافت تاریخی یزد",
                        status="published",
                    )
                )
                await session.commit()

            response = await client.get("/api/v1/listings")
            assert response.status_code == 200, response.text
            titles = [row["title"] for row in response.json()]
            assert titles == ["اقامتگاه منتشرشده"]
            assert LISTING_PAYLOAD["title"] not in titles

    asyncio.run(scenario())


def test_host_dashboard_page_renders():
    async def scenario():
        async with api_client() as (client, _factory):
            response = await client.get("/host")
            assert response.status_code == 200, response.text
            body = response.text
            assert 'id="listing-form"' in body
            assert "#f5f0e6" in body
            assert "http://" not in body and "https://" not in body

    asyncio.run(scenario())
