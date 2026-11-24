"""Phase 3 acceptance tests: seed accounts, admin listings, guest homepage.

Written before the implementation (Iron Rule 1). Runs against an in-memory
SQLite database with ``get_db`` overridden, so ``dev.db`` is never touched.
"""

import asyncio
import importlib
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

ADMIN = {"email": "admin@boom.local", "password": "Admin@1234"}
HOST = {"email": "host@boom.local", "password": "Host@1234"}
GUEST = {"email": "guest@boom.local", "password": "Guest@1234"}

DRAFT_TITLE = "اقامتگاه پیش‌نویس کوهسار"
PUBLISHED_TITLE = "اقامتگاه منتشرشده کویر"


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
        admin = User(
            email=ADMIN["email"],
            password_hash=hash_password(ADMIN["password"]),
            full_name="مدیر سامانه",
            role="admin",
        )
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
        session.add_all([admin, host, guest])
        await session.flush()

        session.add_all(
            [
                Listing(
                    host_id=host.id,
                    title=DRAFT_TITLE,
                    city="کاشان",
                    address="روستای ده‌زیر",
                    status="draft",
                ),
                Listing(
                    host_id=host.id,
                    title=PUBLISHED_TITLE,
                    city="یزد",
                    address="بافت تاریخی یزد",
                    status="published",
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


async def _login(client: AsyncClient, credentials: dict) -> str:
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": credentials["email"], "password": credentials["password"]},
    )
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def test_admin_listings_endpoint_requires_authentication():
    async def scenario():
        async with api_client() as client:
            response = await client.get("/api/v1/listings/admin")
            assert response.status_code == 401, response.text

    asyncio.run(scenario())


def test_non_admin_cannot_list_every_listing():
    async def scenario():
        async with api_client() as client:
            for credentials in (HOST, GUEST):
                token = await _login(client, credentials)
                response = await client.get(
                    "/api/v1/listings/admin",
                    headers={"Authorization": f"Bearer {token}"},
                )
                assert response.status_code == 403, response.text

    asyncio.run(scenario())


def test_admin_sees_every_listing_with_title_city_and_status():
    async def scenario():
        async with api_client() as client:
            token = await _login(client, ADMIN)
            response = await client.get(
                "/api/v1/listings/admin",
                headers={"Authorization": f"Bearer {token}"},
            )
            assert response.status_code == 200, response.text
            rows = {row["title"]: row for row in response.json()}
            assert set(rows) == {DRAFT_TITLE, PUBLISHED_TITLE}
            assert rows[DRAFT_TITLE]["status"] == "draft"
            assert rows[DRAFT_TITLE]["city"] == "کاشان"
            assert rows[PUBLISHED_TITLE]["status"] == "published"

    asyncio.run(scenario())


def test_public_listing_endpoint_still_hides_drafts():
    async def scenario():
        async with api_client() as client:
            response = await client.get("/api/v1/listings")
            assert response.status_code == 200, response.text
            titles = [row["title"] for row in response.json()]
            assert titles == [PUBLISHED_TITLE]

    asyncio.run(scenario())


def test_admin_page_contains_the_listings_view():
    async def scenario():
        async with api_client() as client:
            response = await client.get("/admin")
            assert response.status_code == 200, response.text
            body = response.text
            assert 'id="view-listings"' in body
            assert 'id="listings-body"' in body
            assert 'id="view-dashboard"' in body
            assert "اقامتگاه‌ها" in body
            assert "/api/v1/listings/admin" in body
            assert "http://" not in body and "https://" not in body

    asyncio.run(scenario())


def test_homepage_lists_published_accommodations():
    async def scenario():
        async with api_client() as client:
            response = await client.get("/", follow_redirects=False)
            assert response.status_code == 200, response.text
            body = response.text
            assert 'id="listings-grid"' in body
            assert "#f5f0e6" in body
            assert "/api/v1/listings" in body
            assert "رزرو" in body
            assert "http://" not in body and "https://" not in body

    asyncio.run(scenario())


def test_seed_script_defines_exactly_three_accounts():
    module = importlib.import_module("seed_user")
    seeds = getattr(module, "SEED_USERS", None)
    assert seeds is not None, "seed_user must expose SEED_USERS"
    assert len(seeds) == 3
    by_role = {seed["role"]: seed for seed in seeds}
    assert set(by_role) == {"admin", "host", "guest"}
    assert by_role["admin"]["email"] == "admin@boom.local"
    assert by_role["admin"]["password"] == "Admin@1234"
    assert by_role["host"]["email"] == "host@boom.local"
    assert by_role["host"]["password"] == "Host@1234"
    assert by_role["guest"]["email"] == "guest@boom.local"
    assert by_role["guest"]["password"] == "Guest@1234"
