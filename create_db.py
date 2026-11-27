import asyncio

from app.core.database import Base, engine

# Importing the models registers them on ``Base.metadata``; without these imports
# create_all() would only know about tables it has already seen.
from app.models.booking import Booking  # noqa: F401
from app.models.listing import Listing, Room  # noqa: F401
from app.models.notification import Notification  # noqa: F401
from app.models.user import User  # noqa: F401


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("Database and tables created successfully!")
    print("Tables:", ", ".join(sorted(Base.metadata.tables)))


if __name__ == "__main__":
    asyncio.run(init_db())
