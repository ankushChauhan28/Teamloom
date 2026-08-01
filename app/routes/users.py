from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_user, require_role
from app.db.session import get_db
from app.models.user import User, UserRole
from app.schemas.user import UserRead, UserUpdate

router = APIRouter(prefix="/users", tags=["Users"])


@router.get("/me", response_model=UserRead)
async def get_me(current_user: User = Depends(get_current_user)):
    """
    Retrieve the current logged-in user's profile.
    """
    return current_user


@router.patch("/me", response_model=UserRead)
async def update_me(
    user_update: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Update the basic profile details of the current logged-in user.
    Only allows updating non-sensitive fields (like full_name).
    """
    if user_update.full_name is not None:
        current_user.full_name = user_update.full_name
        await db.commit()
        await db.refresh(current_user)
    return current_user


@router.get("/", response_model=list[UserRead])
async def list_employees(
    db: AsyncSession = Depends(get_db),
    current_admin: User = Depends(require_role(UserRole.ADMIN)),
):
    """
    List all employees in the system. Accessible by Admin only.
    """
    result = await db.execute(select(User).where(User.role == UserRole.EMPLOYEE))
    return list(result.scalars().all())
