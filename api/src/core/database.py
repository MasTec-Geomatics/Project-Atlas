from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from src.core.config import settings

engine = create_engine(str(settings.database_url), pool_pre_ping=True)

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    """Parent class for every table model."""


def get_session() -> Iterator[Session]:
    """FastAPI dependency: one session per request, always closed afterward."""
    with SessionLocal() as session:
        yield session
