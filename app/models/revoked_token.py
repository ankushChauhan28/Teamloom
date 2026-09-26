from sqlalchemy import Column, DateTime, Integer, String
from sqlalchemy.sql import func

from app.db.base import Base


class RevokedToken(Base):
    """
    SQLAlchemy model representing a server-side revoked JWT token (blacklist).
    Stores token_jti and expiration timestamp so expired entries can be pruned cleanly.
    """

    __tablename__ = "revoked_tokens"

    id = Column(Integer, primary_key=True, index=True)
    token_jti = Column(String(255), unique=True, index=True, nullable=False)
    exp_timestamp = Column(DateTime(timezone=True), index=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
