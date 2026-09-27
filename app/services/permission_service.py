"""
Permission Service for Tier Hierarchy and Authority Verification

Provides core helpers for:
- Resolving user access levels
- Direct report retrieval and caching
- Relationship-based management authority verification
- FastAPI dependency for route-level tier enforcement
"""

from collections.abc import Callable
from typing import Any

from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AuthorizationException
from app.core.security import require_password_change_cleared
from app.models.user import User


def get_user_access_level(user: User | None) -> int:
    """
    Returns the integer access tier (1-4) for a given user.
    Falls back gracefully to 1 if role is ADMIN, or 3 if EMPLOYEE.
    """
    if user is None:
        return 4
    if hasattr(user, "role") and user.role is not None:
        role_val = user.role.value if hasattr(user.role, "value") else str(user.role)
        if role_val.upper() == "ADMIN":
            return 1
    if hasattr(user, "access_level") and user.access_level is not None:
        return int(user.access_level)
    return 3


def can_manage_specific_user(
    manager_user: User | None,
    target_user: User | None,
    manager_direct_reports_cached: list[int] | set[int] | None = None,
) -> bool:
    """
    Evaluates whether manager_user has authority to manage target_user for task assignment.
    Rule:
    1. Tier 1 (Admin) can assign tasks to anyone.
    2. Self-management block: actor cannot assign tasks to themselves.
    3. Direct supervisor check: allowed ONLY if target_user.reports_to_id == actor.id
       (or target_user is in cached direct report IDs), regardless of numeric tier.
    """
    if not manager_user or not target_user:
        return False

    # Prevent managing self via supervisor path
    if manager_user.id == target_user.id:
        return False

    manager_base_tier = get_user_access_level(manager_user)
    if manager_base_tier == 1:
        return True

    # Check direct reporting relationship
    is_direct_report = False
    if manager_direct_reports_cached is not None:
        is_direct_report = target_user.id in manager_direct_reports_cached
    elif hasattr(target_user, "reports_to_id"):
        is_direct_report = target_user.reports_to_id == manager_user.id

    return is_direct_report


def check_access_level_dependency(
    required_tier: int, allow_bumping: bool = True
) -> Callable[..., Any]:
    """
    FastAPI dependency factory enforcing a minimum access level tier.
    Note: Lower tier number indicates higher authority (Tier 1 > Tier 2 > Tier 3 > Tier 4).
    """

    async def dependency(
        current_user: User = Depends(require_password_change_cleared),
    ) -> User:
        user_tier = get_user_access_level(current_user)

        # Tier 1 always satisfies any required tier
        if user_tier == 1:
            return current_user

        # If base tier already meets or exceeds the required tier
        if user_tier <= required_tier:
            return current_user

        raise AuthorizationException(
            f"Action requires Tier {required_tier} access level or higher."
        )

    return dependency


async def populate_user_effective_cache(user: User, db: AsyncSession) -> Any:
    """
    Builds UserRead with cached direct reports IDs and access level.
    """
    from app.schemas.user import UserRead

    report_ids_stmt = select(User.id).where(
        User.reports_to_id == user.id,
        User.is_active.is_(True),
    )
    res = await db.execute(report_ids_stmt)
    report_ids = list(res.scalars().all())

    user_read = UserRead.model_validate(user)
    user_read.effective_tier = get_user_access_level(user)
    user_read.direct_reports_ids = report_ids
    return user_read


