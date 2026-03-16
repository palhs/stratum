#!/usr/bin/env python3
"""Checkpoint cleanup — TTL-based purge of langgraph checkpoint tables.

Phase 9 | Plan 03 | Requirement: SRVC-08

Deletes checkpoint records older than CHECKPOINT_TTL_DAYS from all three
langgraph tables. Deletion order: checkpoint_writes, checkpoint_blobs,
checkpoints (no FK cascade exists — manual cascade required).

Environment:
    DATABASE_URL           — PostgreSQL connection string
    CHECKPOINT_TTL_DAYS    — Age threshold in days (default: 7)

Usage:
    python scripts/cleanup-checkpoints.py              # execute cleanup
    python scripts/cleanup-checkpoints.py --dry-run    # preview only
"""

import argparse
import os
import sys

import psycopg

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

TTL_DAYS = int(os.environ.get("CHECKPOINT_TTL_DAYS", "7"))

# ---------------------------------------------------------------------------
# SQL
# ---------------------------------------------------------------------------

COUNT_EXPIRED = """
    SELECT COUNT(DISTINCT thread_id) FROM langgraph.checkpoints
    WHERE created_at < NOW() - make_interval(days => %s)
"""

DELETE_WRITES = """
    DELETE FROM langgraph.checkpoint_writes
    WHERE thread_id IN (
        SELECT DISTINCT thread_id FROM langgraph.checkpoints
        WHERE created_at < NOW() - make_interval(days => %s)
    )
"""

DELETE_BLOBS = """
    DELETE FROM langgraph.checkpoint_blobs
    WHERE thread_id IN (
        SELECT DISTINCT thread_id FROM langgraph.checkpoints
        WHERE created_at < NOW() - make_interval(days => %s)
    )
"""

DELETE_CHECKPOINTS = """
    DELETE FROM langgraph.checkpoints
    WHERE created_at < NOW() - make_interval(days => %s)
"""


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="TTL-based purge of langgraph checkpoint tables.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Environment variables:\n"
            "  DATABASE_URL         PostgreSQL connection string (required)\n"
            "  CHECKPOINT_TTL_DAYS  Age threshold in days (default: 7)\n"
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report how many rows would be deleted without actually deleting.",
    )
    args = parser.parse_args()

    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        print("ERROR: DATABASE_URL environment variable is not set.", file=sys.stderr)
        sys.exit(1)

    with psycopg.connect(database_url) as conn:
        # Count expired threads
        result = conn.execute(COUNT_EXPIRED, (TTL_DAYS,)).fetchone()
        expired_count = result[0] if result else 0

        print(
            f"Found {expired_count} thread(s) with checkpoints older than "
            f"{TTL_DAYS} days."
        )

        if expired_count == 0:
            print("Nothing to clean up.")
            return

        if args.dry_run:
            print("Dry run — no rows deleted.")
            return

        # Execute deletions in cascade order: writes → blobs → checkpoints
        writes_result = conn.execute(DELETE_WRITES, (TTL_DAYS,))
        blobs_result = conn.execute(DELETE_BLOBS, (TTL_DAYS,))
        checkpoints_result = conn.execute(DELETE_CHECKPOINTS, (TTL_DAYS,))

        conn.commit()

        writes_count = writes_result.rowcount
        blobs_count = blobs_result.rowcount
        checkpoints_count = checkpoints_result.rowcount

        print(f"Deleted {writes_count} row(s) from checkpoint_writes.")
        print(f"Deleted {blobs_count} row(s) from checkpoint_blobs.")
        print(f"Deleted {checkpoints_count} row(s) from checkpoints.")
        print(
            f"Cleanup complete: {writes_count + blobs_count + checkpoints_count} "
            f"total rows deleted across {expired_count} thread(s)."
        )


if __name__ == "__main__":
    main()
