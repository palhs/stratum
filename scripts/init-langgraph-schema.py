# scripts/init-langgraph-schema.py
# One-shot init script — creates LangGraph checkpoint tables in 'langgraph' schema
# Runs as Docker init service (langgraph-init) — exits after completion
# Does NOT use AsyncPostgresSaver.setup() (targets public schema only)
# Phase 3 | Plan 03 | Requirement: INFRA-06

import os
import sys

import psycopg

DDL = """
CREATE SCHEMA IF NOT EXISTS langgraph;

CREATE TABLE IF NOT EXISTS langgraph.checkpoint_migrations (
    v INTEGER PRIMARY KEY
);

CREATE TABLE IF NOT EXISTS langgraph.checkpoints (
    thread_id            TEXT NOT NULL,
    checkpoint_ns        TEXT NOT NULL DEFAULT '',
    checkpoint_id        TEXT NOT NULL,
    parent_checkpoint_id TEXT,
    type                 TEXT,
    checkpoint           JSONB NOT NULL,
    metadata             JSONB NOT NULL DEFAULT '{}',
    PRIMARY KEY (thread_id, checkpoint_ns, checkpoint_id)
);

CREATE TABLE IF NOT EXISTS langgraph.checkpoint_blobs (
    thread_id     TEXT  NOT NULL,
    checkpoint_ns TEXT  NOT NULL DEFAULT '',
    channel       TEXT  NOT NULL,
    version       TEXT  NOT NULL,
    type          TEXT  NOT NULL,
    blob          BYTEA,
    PRIMARY KEY (thread_id, checkpoint_ns, channel, version)
);

CREATE TABLE IF NOT EXISTS langgraph.checkpoint_writes (
    thread_id     TEXT    NOT NULL,
    checkpoint_ns TEXT    NOT NULL DEFAULT '',
    checkpoint_id TEXT    NOT NULL,
    task_id       TEXT    NOT NULL,
    idx           INTEGER NOT NULL,
    channel       TEXT    NOT NULL,
    type          TEXT,
    blob          BYTEA   NOT NULL,
    PRIMARY KEY (thread_id, checkpoint_ns, checkpoint_id, task_id, idx)
);
"""

VALIDATION_QUERY = """
SELECT COUNT(*) FROM information_schema.tables
WHERE table_schema = 'langgraph'
  AND table_name IN (
    'checkpoint_migrations',
    'checkpoints',
    'checkpoint_blobs',
    'checkpoint_writes'
  );
"""

EXPECTED_TABLE_COUNT = 4


def main() -> None:
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        print("ERROR: DATABASE_URL environment variable is not set.", file=sys.stderr)
        sys.exit(1)

    print("Connecting to PostgreSQL...")
    try:
        # Use synchronous psycopg3 connection — async is unnecessary for one-shot DDL
        # autocommit=True is required for DDL statements and for checkpoint saver compatibility
        with psycopg.connect(database_url, autocommit=True) as conn:
            print("Executing LangGraph schema DDL...")
            conn.execute(DDL)
            print("DDL executed successfully.")

            print("Validating langgraph schema tables...")
            result = conn.execute(VALIDATION_QUERY).fetchone()
            table_count = result[0] if result else 0

            if table_count != EXPECTED_TABLE_COUNT:
                print(
                    f"ERROR: Expected {EXPECTED_TABLE_COUNT} tables in langgraph schema, "
                    f"found {table_count}.",
                    file=sys.stderr,
                )
                sys.exit(1)

            print(
                f"Validation passed: {table_count} tables confirmed in 'langgraph' schema "
                f"(checkpoint_migrations, checkpoints, checkpoint_blobs, checkpoint_writes)."
            )

    except psycopg.OperationalError as exc:
        print(f"ERROR: Failed to connect to PostgreSQL: {exc}", file=sys.stderr)
        sys.exit(1)
    except psycopg.Error as exc:
        print(f"ERROR: Database error during schema init: {exc}", file=sys.stderr)
        sys.exit(1)

    print("LangGraph schema init complete.")
    sys.exit(0)


if __name__ == "__main__":
    main()
