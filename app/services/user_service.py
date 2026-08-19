from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User, UserRole
from app.schemas.user import UserUpdate


async def update_user_profile(
    db: AsyncSession, user: User, user_update: UserUpdate
) -> User:
    """
    Updates the profile of the target user.
    """
    if user_update.full_name is not None:
        user.full_name = user_update.full_name
        await db.commit()
        await db.refresh(user)
    return user


async def get_employees(db: AsyncSession) -> list[User]:
    """
    Fetches all users with role EMPLOYEE. Admin scope.
    """
    result = await db.execute(select(User).where(User.role == UserRole.EMPLOYEE))
    return list(result.scalars().all())
