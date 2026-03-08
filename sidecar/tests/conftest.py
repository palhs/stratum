"""
Shared test fixtures for the Stratum Data Sidecar test suite.
Phase 2 | Plan 05

Integration test approach:
  - Tests run against the live database (via DATABASE_URL env var).
  - Fixtures provide real SQLAlchemy sessions pointing to the running Postgres instance.
  - Tests validate actual data quality — they are NOT unit tests with mocked data.

Environment:
  DATABASE_URL defaults to postgresql://stratum:changeme@localhost:5432/stratum
  (localhost because tests run outside the container, or inside with the default URL).
"""

import os

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

# ---------------------------------------------------------------------------
# Database URL — allow override for test environment
# ---------------------------------------------------------------------------

_TEST_DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://stratum:changeme@localhost:5432/stratum",
)

# ---------------------------------------------------------------------------
# Session fixture
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def db_engine():
    """Create a SQLAlchemy engine for the test session."""
    engine = create_engine(
        _TEST_DATABASE_URL,
        pool_pre_ping=True,
        pool_size=2,
        max_overflow=0,
    )
    yield engine
    engine.dispose()


@pytest.fixture(scope="function")
def db_session(db_engine):
    """
    Provide a SQLAlchemy session per test function.

    Uses a real database connection — tests read actual ingested data.
    Session is closed (not rolled back) after each test so isolation is
    achieved by querying existing rows, not by mutation.
    """
    SessionLocal = sessionmaker(bind=db_engine, autocommit=False, autoflush=False)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
