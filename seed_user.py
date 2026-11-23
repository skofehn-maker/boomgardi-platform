import asyncio
from app.core.database import AsyncSessionLocal
from app.models.user import User
from app.core.security import hash_password
from sqlalchemy.future import select

async def create_admin():
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(User).where(User.email == "admin@boom.local"))
        if result.scalars().first():
            print("User already exists!")
            return

        admin = User(
            email="admin@boom.local",
            password_hash=hash_password("Admin@1234"),
            full_name="Admin User",
            role="admin"
        )
        db.add(admin)
        await db.commit()
        print("Admin user created successfully!")

if __name__ == "__main__":
    asyncio.run(create_admin())