#!/usr/bin/env python3
# Requires: neo4j>=5.0, python-dotenv>=1.0
"""
seed-neo4j-regimes.py — Seed Neo4j with historical macro regime nodes.
Phase 4 | Plan 01 | Requirement: DATA-01

Usage:
    python scripts/seed-neo4j-regimes.py

Environment:
    NEO4J_URI      — Neo4j bolt URI (default: bolt://neo4j:7687)
    NEO4J_PASSWORD — Neo4j password (required)

Idempotent: MERGE ensures re-runs update existing nodes without duplicates.
"""

import json
import os
import sys
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # python-dotenv optional when running inside Docker

try:
    from neo4j import GraphDatabase
except ImportError:
    print("ERROR: neo4j driver not installed. Run: pip install neo4j>=5.0", file=sys.stderr)
    sys.exit(1)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

NEO4J_URI = os.environ.get("NEO4J_URI", "bolt://neo4j:7687")
NEO4J_USER = os.environ.get("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.environ.get("NEO4J_PASSWORD")

if not NEO4J_PASSWORD:
    print("ERROR: NEO4J_PASSWORD environment variable is required.", file=sys.stderr)
    sys.exit(1)

# Path to regime data JSON — relative to project root
REGIME_DATA_PATH = Path(__file__).parent.parent / "neo4j" / "seed" / "regime_data.json"

# ---------------------------------------------------------------------------
# Seed transaction
# ---------------------------------------------------------------------------

MERGE_REGIMES_QUERY = """
UNWIND $regimes AS row
MERGE (r:Regime {id: row.id})
ON CREATE SET
    r.name          = row.name,
    r.period_start  = row.period_start,
    r.period_end    = row.period_end,
    r.regime_type   = row.regime_type,
    r.gdp_avg       = row.gdp_avg,
    r.cpi_avg       = row.cpi_avg,
    r.unrate_avg    = row.unrate_avg,
    r.fedfunds_avg  = row.fedfunds_avg,
    r.sbv_rate_avg  = row.sbv_rate_avg,
    r.vn_cpi_avg    = row.vn_cpi_avg,
    r.vnd_usd_avg   = row.vnd_usd_avg,
    r.notes         = row.notes,
    r.created_at    = datetime()
ON MATCH SET
    r.name          = row.name,
    r.period_start  = row.period_start,
    r.period_end    = row.period_end,
    r.regime_type   = row.regime_type,
    r.gdp_avg       = row.gdp_avg,
    r.cpi_avg       = row.cpi_avg,
    r.unrate_avg    = row.unrate_avg,
    r.fedfunds_avg  = row.fedfunds_avg,
    r.sbv_rate_avg  = row.sbv_rate_avg,
    r.vn_cpi_avg    = row.vn_cpi_avg,
    r.vnd_usd_avg   = row.vnd_usd_avg,
    r.notes         = row.notes,
    r.updated_at    = datetime()
RETURN r.id AS id
"""


def seed_regimes(tx, regimes: list[dict]) -> list[str]:
    """Transaction function: MERGE all regime nodes, return list of IDs processed."""
    result = tx.run(MERGE_REGIMES_QUERY, regimes=regimes)
    return [record["id"] for record in result]


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    # Load regime data
    if not REGIME_DATA_PATH.exists():
        print(f"ERROR: Regime data not found at {REGIME_DATA_PATH}", file=sys.stderr)
        return 1

    with open(REGIME_DATA_PATH, "r", encoding="utf-8") as f:
        regimes = json.load(f)

    if not regimes:
        print("ERROR: Regime data JSON is empty.", file=sys.stderr)
        return 1

    print(f"Loaded {len(regimes)} regime definitions from {REGIME_DATA_PATH}")
    print(f"Connecting to Neo4j at {NEO4J_URI} ...")

    # Connect and seed
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

    try:
        driver.verify_connectivity()
        print("Connected to Neo4j.")

        with driver.session(database="neo4j") as session:
            seeded_ids = session.execute_write(seed_regimes, regimes)

        print(f"\nSeeded {len(seeded_ids)} regime nodes:")
        for regime_id in seeded_ids:
            print(f"  - {regime_id}")

        print(f"\nDone. {len(seeded_ids)} Regime nodes created/updated in Neo4j.")
        return 0

    except Exception as exc:
        print(f"ERROR: Neo4j seed failed: {exc}", file=sys.stderr)
        return 1

    finally:
        driver.close()


if __name__ == "__main__":
    sys.exit(main())
