"""Seed the three demo accounts: admin, host and guest.

Idempotent: an email that already exists is updated in place instead of
duplicated, so re-running the script is always safe.
"""

import asyncio

from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.core.security import hash_password, verify_password
from app.models.user import User

SEED_USERS = [
    {
        "email": "admin@boom.local",
        "password": "Admin@1234",
        "full_name": "مدیر سامانه",
        "role": "admin",
    },
    {
        "email": "host@boom.local",
        "password": "Host@1234",
        "full_name": "میزبان بوم",
        "role": "host",
    },
    {
        "email": "guest@boom.local",
        "password": "Guest@1234",
        "full_name": "کاربر مهمان",
        "role": "guest",
    },
]


async def seed_users() -> None:
    async with AsyncSessionLocal() as db:
        for seed in SEED_USERS:
            existing = await db.scalar(
                select(User).where(User.email == seed["email"])
            )

            if existing is None:
                db.add(
                    User(
                        email=seed["email"],
                        password_hash=hash_password(seed["password"]),
                        full_name=seed["full_name"],
                        role=seed["role"],
                    )
                )
                print(f"created    {seed['email']:<18} role={seed['role']}")
                continue

            existing.full_name = seed["full_name"]
            existing.role = seed["role"]
            password_changed = False
            if not verify_password(seed["password"], existing.password_hash):
                existing.password_hash = hash_password(seed["password"])
                password_changed = True

            state = "updated   " if password_changed else "unchanged "
            print(f"{state}{seed['email']:<18} role={seed['role']}")

        await db.commit()

    print("Seeded 3 accounts: admin, host, guest.")


if __name__ == "__main__":
    asyncio.run(seed_users())
