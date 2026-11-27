"""Registration page and self-service sign-up behaviour."""

import asyncio
from contextlib import asynccontextmanager

from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
from app.main import app
from app.models.user import User


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


def test_register_page_renders_form():
    async def scenario():
        async with api_client() as (client, _):
            response = await client.get("/register")
            assert response.status_code == 200
            html = response.text
            assert 'dir="rtl"' in html
            assert 'id="register-form"' in html
            assert 'name="full_name"' in html
            assert 'name="email"' in html
            assert 'name="password"' in html
            assert 'name="role"' in html
            assert 'value="guest"' in html and 'value="host"' in html
            assert "/api/v1/auth/register" in html
            assert "http://" not in html and "https://" not in html

    asyncio.run(scenario())


def test_register_page_links_to_login():
    async def scenario():
        async with api_client() as (client, _):
            response = await client.get("/register")
            assert 'href="/login"' in response.text

    asyncio.run(scenario())


def test_login_page_links_to_register():
    async def scenario():
        async with api_client() as (client, _):
            response = await client.get("/login")
            assert response.status_code == 200
            assert 'href="/register"' in response.text
            assert "حساب کاربری ندارید؟ ثبت‌نام کنید" in response.text

    asyncio.run(scenario())


def test_register_persists_full_name_and_role():
    async def scenario():
        async with api_client() as (client, session_factory):
            response = await client.post(
                "/api/v1/auth/register",
                json={
                    "full_name": "  مریم احمدی  ",
                    "email": "Maryam@Boom.local",
                    "password": "Maryam@1234",
                    "role": "host",
                },
            )
            assert response.status_code == 201, response.text
            body = response.json()
            assert body["email"] == "maryam@boom.local"
            assert body["full_name"] == "مریم احمدی"
            assert body["role"] == "host"
            assert "password" not in body

            async with session_factory() as session:
                user = await session.scalar(
                    select(User).where(User.email == "maryam@boom.local")
                )
                assert user is not None
                assert user.role == "host"
                assert user.full_name == "مریم احمدی"

    asyncio.run(scenario())


def test_register_defaults_to_guest():
    async def scenario():
        async with api_client() as (client, _):
            response = await client.post(
                "/api/v1/auth/register",
                json={"email": "plain@boom.local", "password": "Plain@1234"},
            )
            assert response.status_code == 201, response.text
            assert response.json()["role"] == "guest"

    asyncio.run(scenario())


def test_register_rejects_admin_role():
    async def scenario():
        async with api_client() as (client, _):
            response = await client.post(
                "/api/v1/auth/register",
                json={
                    "email": "sneaky@boom.local",
                    "password": "Sneaky@1234",
                    "role": "admin",
                },
            )
            assert response.status_code == 422

    asyncio.run(scenario())


def test_register_rejects_short_password():
    async def scenario():
        async with api_client() as (client, _):
            response = await client.post(
                "/api/v1/auth/register",
                json={"email": "short@boom.local", "password": "short"},
            )
            assert response.status_code == 422

    asyncio.run(scenario())


def test_register_rejects_duplicate_email():
    async def scenario():
        async with api_client() as (client, _):
            payload = {"email": "dupe@boom.local", "password": "Dupe@12345"}
            first = await client.post("/api/v1/auth/register", json=payload)
            assert first.status_code == 201
            second = await client.post("/api/v1/auth/register", json=payload)
            assert second.status_code == 400

    asyncio.run(scenario())
