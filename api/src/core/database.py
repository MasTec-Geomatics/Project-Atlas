from collections.abc import Iterator

from sqlalchemy import MetaData, create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from src.core.config import settings

# Constraint naming convention (ADR 0015).
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

# atlas database
engine = create_engine(str(settings.database_url), pool_pre_ping=True)

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    """Parent class for every atlas table model."""


def get_session() -> Iterator[Session]:
    """FastAPI dependency: one atlas session per request, always closed afterward"""
    with SessionLocal() as session:
        yield session


# reference database (ADR 0017)
reference_engine = create_engine(str(settings.reference_database_url), pool_pre_ping=True)

ReferenceSessionLocal = sessionmaker(bind=reference_engine, autoflush=False, expire_on_commit=False)


class ReferenceBase(DeclarativeBase):
    """Parent class for every reference table model."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)


def get_reference_session() -> Iterator[Session]:
    """FastAPI dependency: one reference session per request, always closed afterward."""
    with ReferenceSessionLocal() as session:
        yield session
