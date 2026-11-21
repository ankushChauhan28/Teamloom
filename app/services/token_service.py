import hashlib
import secrets
from datetime import UTC, datetime, timedelta

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequestException
from app.models.user_token import UserToken

GENERIC_TOKEN_ERROR = "Invalid or expired token."


async def generate_user_token(
    db: AsyncSession, user_id: int, token_type: str, expire_hours: int
) -> str:
    """
    Generates a cryptographically secure 32-byte urlsafe token,
    hashes it via SHA-256, invalidates any existing unused tokens of the same
    type for this user, and inserts the new token record.
    Returns the raw unhashed token string to be dispatched in email.
    """
    raw_token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
    now = datetime.now(UTC)
    expires_at = now + timedelta(hours=expire_hours)

    # Invalidate existing unused tokens of this type for this user
    await db.execute(
        update(UserToken)
        .where(
            UserToken.user_id == user_id,
            UserToken.token_type == token_type,
            UserToken.used_at.is_(None),
        )
        .values(used_at=now)
    )

    token_record = UserToken(
        user_id=user_id,
        token_hash=token_hash,
        token_type=token_type,
        expires_at=expires_at,
        used_at=None,
    )
    db.add(token_record)
    await db.flush()
    return raw_token


async def consume_token(
    db: AsyncSession, raw_token: str, token_type: str
) -> UserToken:
    """
    Atomically validates and consumes a token in a single statement:
    UPDATE ... WHERE token_hash == :hash AND token_type == :type AND used_at IS NULL AND expires_at > now() RETURNING ...
    Guarantees strict single-use semantics even under concurrent attempts.
    Raises BadRequestException with generic message on any failure.
    """
    if not raw_token or not raw_token.strip():
        raise BadRequestException(GENERIC_TOKEN_ERROR)

    token_hash = hashlib.sha256(raw_token.strip().encode("utf-8")).hexdigest()
    now = datetime.now(UTC)

    stmt = (
        update(UserToken)
        .where(
            UserToken.token_hash == token_hash,
            UserToken.token_type == token_type,
            UserToken.used_at.is_(None),
            UserToken.expires_at > now,
        )
        .values(used_at=now)
        .returning(UserToken)
    )
    result = await db.execute(stmt)
    token_record = result.scalar_one_or_none()

    if not token_record:
        raise BadRequestException(GENERIC_TOKEN_ERROR)

    return token_record


async def invalidate_user_tokens(
    db: AsyncSession, user_id: int, token_type: str | None = None
) -> None:
    """
    Marks all unused tokens for the user (optionally of a specific token_type) as used.
    """
    now = datetime.now(UTC)
    conditions = [UserToken.user_id == user_id, UserToken.used_at.is_(None)]
    if token_type is not None:
        conditions.append(UserToken.token_type == token_type)

    await db.execute(update(UserToken).where(*conditions).values(used_at=now))
