from typing import Any, Type, TypeVar

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ResourceNotFoundException

T = TypeVar("T")


async def get_scoped_or_404(
    db: AsyncSession,
    model: Type[T],
    id_val: Any,
    organization_id: int | None,
    error_msg: str | None = None,
) -> T:
    """
    Looks up a database entity by primary key (id) and organization_id.
    If the entity is not found or belongs to a different organization,
    raises ResourceNotFoundException (404) with an identical error message
    so that cross-tenant resource existence is never revealed.
    """
    conditions = [model.id == id_val]
    if organization_id is not None and hasattr(model, "organization_id"):
        conditions.append(model.organization_id == organization_id)

    stmt = select(model).where(*conditions)
    result = await db.execute(stmt)
    obj = result.scalar_one_or_none()
    if not obj:
        if error_msg is None:
            model_name = getattr(model, "__name__", "Resource")
            if model_name == "User":
                error_msg = "User not found."
            elif model_name == "Task":
                error_msg = f"Task with ID {id_val} not found."
            elif model_name == "LeaveRequest":
                error_msg = f"Leave request with ID {id_val} not found."
            else:
                error_msg = f"{model_name} not found."
        raise ResourceNotFoundException(error_msg)
    return obj
