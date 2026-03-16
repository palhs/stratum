"""
FastAPI lifespan context manager for reasoning-engine.

Initializes shared resources on startup and tears them down on shutdown:
  - db_engine: SQLAlchemy Engine for PostgreSQL (sync, for report reads/writes)
  - neo4j_driver: Neo4j GraphDatabase driver
  - qdrant_client: Qdrant vector store client
  - db_uri: raw DATABASE_URL string (for AsyncPostgresSaver in run_graph)
  - job_queues: per-job asyncio.Queue for SSE progress streaming (Plan 03)
"""
import asyncio
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from neo4j import GraphDatabase
from qdrant_client import QdrantClient
from sqlalchemy import create_engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: initialize and dispose shared resources."""
    # --- Startup ---
    database_url = os.environ["DATABASE_URL"]
    app.state.db_engine = create_engine(
        database_url,
        pool_pre_ping=True,
        pool_size=5,
    )
    app.state.db_uri = database_url

    neo4j_uri = os.environ["NEO4J_URI"]
    neo4j_password = os.environ["NEO4J_PASSWORD"]
    app.state.neo4j_driver = GraphDatabase.driver(
        neo4j_uri,
        auth=("neo4j", neo4j_password),
    )

    qdrant_host = os.environ["QDRANT_HOST"]
    qdrant_port = int(os.environ.get("QDRANT_PORT", "6333"))
    qdrant_api_key = os.environ.get("QDRANT_API_KEY") or None
    app.state.qdrant_client = QdrantClient(
        host=qdrant_host,
        port=qdrant_port,
        api_key=qdrant_api_key,
    )

    # SSE progress queues — keyed by job_id (int)
    app.state.job_queues: dict[int, asyncio.Queue] = {}

    yield

    # --- Shutdown ---
    app.state.db_engine.dispose()
    app.state.neo4j_driver.close()
