"""
Permission Service for Tier Hierarchy and Dynamic Authority Bumping (Option B)

Provides core helpers for:
- Resolving base and effective access levels with dynamic authority bumping
- Direct report retrieval and caching
- Relationship and tier-based management authority verification
- FastAPI dependency for route-level tier enforcement
"""

from collections.abc import Callable
from typing import Any

from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AuthorizationException
from app.core.permissions import (
    BASE_TIER_MANAGING_RULES,
    TIER_BUMPING_RULES,
)
from app.core.security import require_password_change_cleared
from app.models.user import User, UserRole


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


def get_effective_tier(user: User | None, has_direct_reports: bool = False) -> int:
    """
    Calculates the effective operational tier for a user.
    If the user has direct reports, applies dynamic authority bumping:
    - Tier 3 with reports bumps to Tier 2 authority
    - Tier 4 with reports bumps to Tier 3 authority
    - Tiers 1 and 2 remain unaffected
    """
    base_tier = get_user_access_level(user)
    if has_direct_reports and base_tier in TIER_BUMPING_RULES:
        return TIER_BUMPING_RULES[base_tier]
    return base_tier



def can_manage_specific_user(
    manager_user: User | None,
    target_user: User | None,
    manager_direct_reports_cached: list[int] | set[int] | None = None,
) -> bool:
    """
    Evaluates whether manager_user has authority to manage target_user.
    Considers:
    1. Executive / Tier 1 authority (Tier 1 can manage any user except self-assignment blocks handled at service).
    2. Self-management block (manager cannot manage themselves via managerial paths).
    3. Direct supervisor relationship (either in cached direct report IDs or via reports_to_id).
    4. Tier hierarchy: effective tier must be eligible to manage target tier under BASE_TIER_MANAGING_RULES.
    """
    if not manager_user or not target_user:
        return False

    # Prevent managing self via supervisor path
    if manager_user.id == target_user.id:
        return False

    manager_base_tier = get_user_access_level(manager_user)
    if manager_base_tier == 1:
        return True

    target_tier = get_user_access_level(target_user)

    # Check direct reporting relationship
    is_direct_report = False
    if manager_direct_reports_cached is not None:
        is_direct_report = target_user.id in manager_direct_reports_cached
    elif hasattr(target_user, "reports_to_id"):
        is_direct_report = target_user.reports_to_id == manager_user.id

    if not is_direct_report:
        return False

    # Effective tier with bumping applied because manager has at least this direct report
    effective_tier = get_effective_tier(manager_user, has_direct_reports=True)

    # Check if target tier is allowed by managing tier rules
    allowed_tiers = BASE_TIER_MANAGING_RULES.get(effective_tier, set())
    return target_tier in allowed_tiers



from app.db.session import get_db


def check_access_level_dependency(
    required_tier: int, allow_bumping: bool = True
) -> Callable[..., Any]:
    """
    FastAPI dependency factory enforcing a minimum access level tier.
    Note: Lower tier number indicates higher authority (Tier 1 > Tier 2 > Tier 3 > Tier 4).
    """

    async def dependency(
        current_user: User = Depends(require_password_change_cleared),
        db: AsyncSession = Depends(get_db),
    ) -> User:
        user_tier = get_user_access_level(current_user)

        # Tier 1 always satisfies any required tier
        if user_tier == 1:
            return current_user

        # If base tier already meets or exceeds the required tier
        if user_tier <= required_tier:
            return current_user

        # If bumping allowed and user has reports, evaluate effective tier
        if allow_bumping and user_tier in TIER_BUMPING_RULES:
            # Query direct reports using async db session to avoid MissingGreenlet
            stmt = select(User.id).where(
                User.reports_to_id == current_user.id,
                User.is_active.is_(True),
            ).limit(1)
            res = await db.execute(stmt)
            if res.scalar_one_or_none() is not None:
                effective_tier = TIER_BUMPING_RULES[user_tier]
                if effective_tier <= required_tier:
                    return current_user

        raise AuthorizationException(
            f"Action requires Tier {required_tier} access level or higher."
        )

    return dependency


async def populate_user_effective_cache(user: User, db: AsyncSession) -> Any:
    """
    Builds UserRead with cached direct reports IDs and dynamically bumped effective tier.
    """
    from app.schemas.user import UserRead

    report_ids_stmt = select(User.id).where(
        User.reports_to_id == user.id,
        User.is_active.is_(True),
    )
    res = await db.execute(report_ids_stmt)
    report_ids = list(res.scalars().all())

    effective_tier = get_effective_tier(user, has_direct_reports=len(report_ids) > 0)
    user_read = UserRead.model_validate(user)
    user_read.effective_tier = effective_tier
    user_read.direct_reports_ids = report_ids
    return user_read

