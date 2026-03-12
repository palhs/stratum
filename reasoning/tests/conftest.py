"""
reasoning/tests/conftest.py — Shared fixtures for live Docker service integration tests.
Phase 5 | Plan 01

All fixtures read from environment variables with defaults matching docker-compose.yml
service names. Use session scope for expensive resources (driver/engine).

Usage:
    These fixtures are for integration tests that require live Docker services.
    Unit tests (test_freshness.py) do not need these fixtures.
"""

import os
import pytest
from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# Environment defaults (matching docker-compose.yml service names)
# ---------------------------------------------------------------------------

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://neo4j:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "stratum_neo4j_password")

QDRANT_HOST = os.getenv("QDRANT_HOST", "qdrant")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", "6333"))
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY", "")
QDRANT_HTTPS = os.getenv("QDRANT_HTTPS", "false").lower() in ("true", "1", "yes")

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://stratum:stratum_password@postgres:5432/stratum"
)


# ---------------------------------------------------------------------------
# Neo4j fixture
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def neo4j_driver():
    """
    Session-scoped Neo4j driver fixture.
    Connects once per test session — expensive to create, cheap to reuse.
    """
    from neo4j import GraphDatabase

    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    try:
        driver.verify_connectivity()
    except Exception as exc:
        pytest.skip(f"Neo4j not available at {NEO4J_URI}: {exc}")
    yield driver
    driver.close()


# ---------------------------------------------------------------------------
# Qdrant fixture
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def qdrant_client():
    """
    Session-scoped Qdrant client fixture.
    """
    from qdrant_client import QdrantClient

    client = QdrantClient(
        host=QDRANT_HOST,
        port=QDRANT_PORT,
        api_key=QDRANT_API_KEY if QDRANT_API_KEY else None,
        https=QDRANT_HTTPS,
    )
    try:
        client.get_collections()
    except Exception as exc:
        pytest.skip(f"Qdrant not available at {QDRANT_HOST}:{QDRANT_PORT}: {exc}")
    yield client


# ---------------------------------------------------------------------------
# PostgreSQL fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def db_engine():
    """
    Session-scoped SQLAlchemy engine fixture.
    """
    from sqlalchemy import create_engine

    engine = create_engine(
        DATABASE_URL,
        pool_pre_ping=True,
        pool_size=5,
    )
    try:
        with engine.connect() as conn:
            from sqlalchemy import text
            conn.execute(text("SELECT 1"))
    except Exception as exc:
        pytest.skip(f"PostgreSQL not available at DATABASE_URL: {exc}")
    yield engine
    engine.dispose()


@pytest.fixture(scope="function")
def db_session(db_engine):
    """
    Function-scoped SQLAlchemy session fixture.
    Creates a new session per test, rolls back after each test.
    """
    from sqlalchemy.orm import sessionmaker

    SessionLocal = sessionmaker(bind=db_engine, autocommit=False, autoflush=False)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
