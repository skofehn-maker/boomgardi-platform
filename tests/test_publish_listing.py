"""Phase 4 acceptance tests: publishing a draft listing.

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
from app.models.listing import Listing
from app.models.user import User

HOST = {"email": "host@boom.local", "password": "Host@1234"}
OTHER_HOST = {"email": "other@boom.local", "password": "Other@1234"}
GUEST = {"email": "guest@boom.local", "password": "Guest@1234"}


@asynccontextmanager
async def api_client():
    """Yield ``(client, session_factory, ids)`` with a fresh in-memory database."""
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

        draft = Listing(
            host_id=host.id,
            title="اقامتگاه پیش‌نویس کوهسار",
            city="کاشان",
            address="روستای ده‌زیر",
            status="draft",
        )
        foreign = Listing(
            host_id=other.id,
            title="اقامتگاه میزبان دیگر",
            city="یزد",
            address="بافت تاریخی",
            status="draft",
        )
        session.add_all([draft, foreign])
        await session.commit()

        ids["draft"] = draft.id
        ids["foreign"] = foreign.id

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


def test_publish_requires_authentication():
    async def scenario():
        async with api_client() as (client, _factory, ids):
            response = await client.patch(
                f"/api/v1/listings/{ids['draft']}/publish",
                headers=_headers(key=str(uuid.uuid4())),
            )
            assert response.status_code == 401, response.text

    asyncio.run(scenario())


def test_publish_requires_idempotency_key():
    async def scenario():
        async with api_client() as (client, _factory, ids):
            token = await _login(client, HOST)
            response = await client.patch(
                f"/api/v1/listings/{ids['draft']}/publish",
                headers=_headers(token),
            )
            assert response.status_code == 422, response.text

    asyncio.run(scenario())


def test_host_publishes_own_draft():
    async def scenario():
        async with api_client() as (client, factory, ids):
            token = await _login(client, HOST)
            response = await client.patch(
                f"/api/v1/listings/{ids['draft']}/publish",
                headers=_headers(token, str(uuid.uuid4())),
            )
            assert response.status_code == 200, response.text
            body = response.json()
            assert body["id"] == str(ids["draft"])
            assert body["status"] == "published"
            assert body["title"] == "اقامتگاه پیش‌نویس کوهسار"

            public = await client.get("/api/v1/listings")
            assert public.status_code == 200, public.text
            assert [row["title"] for row in public.json()] == ["اقامتگاه پیش‌نویس کوهسار"]

    asyncio.run(scenario())


def test_publishing_twice_is_idempotent():
    async def scenario():
        async with api_client() as (client, _factory, ids):
            token = await _login(client, HOST)
            url = f"/api/v1/listings/{ids['draft']}/publish"

            first = await client.patch(url, headers=_headers(token, str(uuid.uuid4())))
            second = await client.patch(url, headers=_headers(token, str(uuid.uuid4())))

            assert first.status_code == 200, first.text
            assert second.status_code == 200, second.text
            assert first.json()["status"] == second.json()["status"] == "published"
            assert first.json()["id"] == second.json()["id"]

    asyncio.run(scenario())


def test_host_cannot_publish_another_hosts_listing():
    async def scenario():
        async with api_client() as (client, factory, ids):
            token = await _login(client, HOST)
            response = await client.patch(
                f"/api/v1/listings/{ids['foreign']}/publish",
                headers=_headers(token, str(uuid.uuid4())),
            )
            assert response.status_code == 403, response.text

            async with factory() as session:
                awaited = await session.get(Listing, ids["foreign"])
                assert awaited.status == "draft"

    asyncio.run(scenario())


def test_publish_unknown_listing_returns_404():
    async def scenario():
        async with api_client() as (client, _factory, _ids):
            token = await _login(client, HOST)
            response = await client.patch(
                f"/api/v1/listings/{uuid.uuid4()}/publish",
                headers=_headers(token, str(uuid.uuid4())),
            )
            assert response.status_code == 404, response.text

    asyncio.run(scenario())


def test_my_listings_returns_only_the_callers_rows():
    async def scenario():
        async with api_client() as (client, _factory, ids):
            anonymous = await client.get("/api/v1/listings/mine")
            assert anonymous.status_code == 401, anonymous.text

            token = await _login(client, HOST)
            response = await client.get(
                "/api/v1/listings/mine", headers=_headers(token)
            )
            assert response.status_code == 200, response.text
            rows = response.json()
            assert [row["id"] for row in rows] == [str(ids["draft"])]
            assert rows[0]["status"] == "draft"

    asyncio.run(scenario())


def test_host_page_offers_the_publish_action():
    async def scenario():
        async with api_client() as (client, _factory, _ids):
            response = await client.get("/host")
            assert response.status_code == 200, response.text
            body = response.text
            assert 'id="my-listings-body"' in body
            assert "/api/v1/listings/mine" in body
            assert "/publish" in body
            assert "انتشار" in body
            assert "http://" not in body and "https://" not in body

    asyncio.run(scenario())
