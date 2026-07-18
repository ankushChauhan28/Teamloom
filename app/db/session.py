from typing import Generator
from sqlalchemy.orm import Session
from app.db.base import SessionLocal

def get_db() -> Generator[Session, None, None]:
    """
    FastAPI dependency that yields a SQLAlchemy database session
    and ensures it is closed after the request is processed.
    """
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()
