"""
Database connection management for the Stratum Data Sidecar.
Phase 2 | Plan 01

Reads DATABASE_URL from environment.
Default: postgresql://stratum:changeme@postgres:5432/stratum
(matches docker-compose.yml service name and .env.example defaults)
"""

import os
from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

DATABASE_URL: str = os.environ.get(
    "DATABASE_URL",
    "postgresql://stratum:changeme@postgres:5432/stratum",
)

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,   # Detect stale connections before use
    pool_size=5,
    max_overflow=10,
)

SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
)


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency that provides a SQLAlchemy session per request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
