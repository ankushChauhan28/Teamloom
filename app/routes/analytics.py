from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import require_password_change_cleared
from app.db.session import get_db
from app.models.user import User
from app.schemas.analytics import PerformanceStats
from app.services import analytics_service

router = APIRouter(prefix="/analytics", tags=["Analytics"])


@router.get("/performance", response_model=PerformanceStats)
async def get_performance_analytics(
    employee_id: int | None = None,
    trail_limit: int = 10,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_password_change_cleared),
):
    """
    Retrieve performance analytics for the authenticated user, team, organization, or specified employee.
    Includes on-time completion rate, classified task counts, and a milestone trail of recent tasks.
    """
    return await analytics_service.get_performance_analytics(
        db=db,
        user=current_user,
        employee_id=employee_id,
        trail_limit=trail_limit,
    )
