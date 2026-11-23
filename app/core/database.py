from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase
from app.core.config import settings

# ساخت موتور دیتابیس
engine = create_async_engine(settings.DATABASE_URL, echo=True)

# ساخت سازنده نشست (Session)
AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

# این کلاس Base برای ساخت جدول‌ها حیاتی است
class Base(DeclarativeBase):
    pass

# وابستگی برای گرفتن دیتابیس در مسیرهای FastAPI
async def get_db():
    async with AsyncSessionLocal() as session:
        yield session