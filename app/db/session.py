from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import AsyncSessionLocal


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI async dependency that yields an AsyncSession database session
    and ensures it is closed after the request is processed.
    """
    async with AsyncSessionLocal() as session:
        yield session
