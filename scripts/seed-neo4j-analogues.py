#!/usr/bin/env python3
"""
seed-neo4j-analogues.py — Compute regime similarity and seed HAS_ANALOGUE relationships.
Phase 4 | Plan 02 | Requirement: DATA-02

Usage:
    python scripts/seed-neo4j-analogues.py

Requires regime nodes to exist (run seed-neo4j-regimes.py first).
Idempotent: MERGE ensures re-runs update existing relationships.
Gemini narratives are cached to neo4j/seed/analogue_narratives.json.
"""

# Requires: neo4j>=5.0, numpy, scipy, scikit-learn, google-generativeai, python-dotenv

import json
import logging
import os
import time
from pathlib import Path

import numpy as np
from dotenv import load_dotenv
from neo4j import GraphDatabase
from scipy.spatial.distance import cdist
from sklearn.preprocessing import MinMaxScaler

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

SIMILARITY_THRESHOLD = 0.75
TOP_N_ANALOGUES = 5
GEMINI_MODEL = "gemini-2.5-flash"
NARRATIVE_CACHE_PATH = Path("neo4j/seed/analogue_narratives.json")
REGIME_DATA_PATH = Path("neo4j/seed/regime_data.json")
FRED_DIMENSIONS = ["gdp_avg", "cpi_avg", "unrate_avg", "fedfunds_avg"]

GEMINI_PROMPT_TEMPLATE = """You are a macroeconomic analyst. Compare these two economic periods:

Period A: {name_a} ({period_start_a} to {period_end_a})
- GDP growth: {gdp_a}%, CPI: {cpi_a}%, Unemployment: {unrate_a}%, Fed Funds: {fedfunds_a}%
- Context: {notes_a}

Period B: {name_b} ({period_start_b} to {period_end_b})
- GDP growth: {gdp_b}%, CPI: {cpi_b}%, Unemployment: {unrate_b}%, Fed Funds: {fedfunds_b}%
- Context: {notes_b}

Cosine similarity: {similarity_score:.3f}

In 2-3 sentences, explain the key macroeconomic parallels between these periods that make them useful historical analogues for investment analysis. Focus on policy environment, growth trajectory, and inflation dynamics."""

MERGE_CYPHER = """
UNWIND $batch AS row
MATCH (src:Regime {id: row.from_id})
MATCH (tgt:Regime {id: row.to_id})
MERGE (src)-[rel:HAS_ANALOGUE]->(tgt)
SET rel.similarity_score   = row.similarity_score,
    rel.dimensions_matched = row.dimensions_matched,
    rel.period_start       = row.period_start,
    rel.period_end         = row.period_end,
    rel.narrative          = row.narrative
"""


# ---------------------------------------------------------------------------
# Step 1: Load regime data and build feature vectors
# ---------------------------------------------------------------------------


def load_regimes(path: Path) -> tuple[list[dict], list[dict], np.ndarray]:
    """Load regime data, filter for complete FRED vectors, return feature matrix."""
    with open(path) as f:
        all_regimes = json.load(f)

    complete = []
    for r in all_regimes:
        missing = [dim for dim in FRED_DIMENSIONS if r.get(dim) is None]
        if missing:
            log.warning(
                "Excluding regime '%s' from similarity computation — null FRED dims: %s",
                r["id"],
                missing,
            )
        else:
            complete.append(r)

    log.info("Regimes with complete FRED data: %d / %d", len(complete), len(all_regimes))

    feature_matrix = np.array([[r[dim] for dim in FRED_DIMENSIONS] for r in complete])
    return all_regimes, complete, feature_matrix


# ---------------------------------------------------------------------------
# Step 2: Compute normalized pairwise cosine similarity
# ---------------------------------------------------------------------------


def compute_similarity(feature_matrix: np.ndarray) -> np.ndarray:
    """Normalize feature vectors and compute cosine similarity matrix."""
    scaler = MinMaxScaler()
    normalized = scaler.fit_transform(feature_matrix)
    log.info("Feature matrix shape: %s", feature_matrix.shape)
    log.info("Normalized value range: [%.4f, %.4f]", normalized.min(), normalized.max())

    distance_matrix = cdist(normalized, normalized, metric="cosine")
    sim_matrix = 1.0 - distance_matrix

    log.info("Similarity matrix shape: %s", sim_matrix.shape)
    log.info(
        "Similarity value range (excluding diagonal): min=%.4f max=%.4f",
        sim_matrix[sim_matrix < 0.9999].min(),
        sim_matrix[sim_matrix < 0.9999].max(),
    )
    return sim_matrix


# ---------------------------------------------------------------------------
# Step 3: Select top analogues per regime (threshold-filtered)
# ---------------------------------------------------------------------------


def select_analogues(
    regimes: list[dict], sim_matrix: np.ndarray, threshold: float, top_n: int
) -> list[dict]:
    """Build list of analogue pairs above threshold, top N per regime."""
    pairs = []
    n = len(regimes)

    for i in range(n):
        # Collect candidates: all other regimes above threshold, sorted desc
        candidates = []
        for j in range(n):
            if i == j:
                continue
            score = float(sim_matrix[i, j])
            if score >= threshold:
                candidates.append((score, j))

        candidates.sort(key=lambda x: x[0], reverse=True)
        top_candidates = candidates[:top_n]

        if len(top_candidates) < 2:
            log.warning(
                "Regime '%s' has only %d analogue(s) above threshold %.2f — sparse connectivity accepted",
                regimes[i]["id"],
                len(top_candidates),
                threshold,
            )

        for score, j in top_candidates:
            pairs.append(
                {
                    "from_id": regimes[i]["id"],
                    "to_id": regimes[j]["id"],
                    "similarity_score": score,
                    "dimensions_matched": FRED_DIMENSIONS,
                    "period_start": regimes[i]["period_start"],
                    "period_end": regimes[i]["period_end"],
                }
            )

    log.info(
        "Selected %d analogue pairs (threshold=%.2f, top_n=%d)", len(pairs), threshold, top_n
    )
    return pairs


# ---------------------------------------------------------------------------
# Step 4: Generate static narratives via Gemini API (with caching)
# ---------------------------------------------------------------------------


def load_narrative_cache(path: Path) -> dict:
    """Load existing narrative cache (key = from_id::to_id)."""
    if path.exists():
        with open(path) as f:
            cache = json.load(f)
        log.info("Loaded %d cached narratives from %s", len(cache), path)
        return cache
    return {}


def save_narrative_cache(path: Path, cache: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(cache, f, indent=2)


def call_gemini_with_retry(model, prompt: str, max_retries: int = 3) -> str:
    """Call Gemini with exponential backoff on failure."""
    delay = 2
    for attempt in range(max_retries):
        try:
            response = model.generate_content(prompt)
            return response.text.strip()
        except Exception as exc:
            if attempt < max_retries - 1:
                log.warning(
                    "Gemini call failed (attempt %d/%d): %s — retrying in %ds",
                    attempt + 1,
                    max_retries,
                    exc,
                    delay,
                )
                time.sleep(delay)
                delay *= 2
            else:
                log.error("Gemini call failed after %d retries: %s", max_retries, exc)
                return "Narrative generation failed — manual review needed"


def generate_narratives(
    pairs: list[dict],
    regime_lookup: dict,
    cache: dict,
    gemini_api_key: str | None,
) -> tuple[list[dict], dict]:
    """Generate or retrieve cached narratives for each analogue pair."""
    if not gemini_api_key:
        log.warning(
            "GEMINI_API_KEY not set — skipping narrative generation; narrative will be empty string"
        )
        for pair in pairs:
            pair["narrative"] = ""
        return pairs, cache

    import google.generativeai as genai

    genai.configure(api_key=gemini_api_key)
    model = genai.GenerativeModel(GEMINI_MODEL)

    new_calls = 0
    for pair in pairs:
        cache_key = f"{pair['from_id']}::{pair['to_id']}"
        if cache_key in cache:
            pair["narrative"] = cache[cache_key]
            continue

        regime_a = regime_lookup[pair["from_id"]]
        regime_b = regime_lookup[pair["to_id"]]

        prompt = GEMINI_PROMPT_TEMPLATE.format(
            name_a=regime_a["name"],
            period_start_a=regime_a["period_start"],
            period_end_a=regime_a["period_end"],
            gdp_a=regime_a["gdp_avg"],
            cpi_a=regime_a["cpi_avg"],
            unrate_a=regime_a["unrate_avg"],
            fedfunds_a=regime_a["fedfunds_avg"],
            notes_a=regime_a["notes"],
            name_b=regime_b["name"],
            period_start_b=regime_b["period_start"],
            period_end_b=regime_b["period_end"],
            gdp_b=regime_b["gdp_avg"],
            cpi_b=regime_b["cpi_avg"],
            unrate_b=regime_b["unrate_avg"],
            fedfunds_b=regime_b["fedfunds_avg"],
            notes_b=regime_b["notes"],
            similarity_score=pair["similarity_score"],
        )

        narrative = call_gemini_with_retry(model, prompt)
        pair["narrative"] = narrative
        cache[cache_key] = narrative
        new_calls += 1

        # Rate limit protection
        time.sleep(1)

    if new_calls > 0:
        save_narrative_cache(NARRATIVE_CACHE_PATH, cache)
        log.info("Generated %d new narratives (cache updated)", new_calls)
    else:
        log.info("All narratives served from cache — no Gemini API calls made")

    return pairs, cache


# ---------------------------------------------------------------------------
# Step 5: MERGE HAS_ANALOGUE relationships into Neo4j
# ---------------------------------------------------------------------------


def merge_analogues(driver, pairs: list[dict]) -> None:
    """MERGE HAS_ANALOGUE relationships via UNWIND batch pattern."""
    batch = [
        {
            "from_id": p["from_id"],
            "to_id": p["to_id"],
            "similarity_score": p["similarity_score"],
            "dimensions_matched": p["dimensions_matched"],
            "period_start": p["period_start"],
            "period_end": p["period_end"],
            "narrative": p["narrative"],
        }
        for p in pairs
    ]

    with driver.session() as session:
        session.run(MERGE_CYPHER, batch=batch)
    log.info("MERGE complete: %d HAS_ANALOGUE relationships written", len(batch))


# ---------------------------------------------------------------------------
# Step 6: Validate after write
# ---------------------------------------------------------------------------


def validate_relationships(driver, pairs: list[dict]) -> None:
    """Run post-write validation queries."""
    with driver.session() as session:
        # Check for missing required properties
        null_count_result = session.run(
            """
            MATCH ()-[r:HAS_ANALOGUE]->()
            WHERE r.similarity_score IS NULL OR r.dimensions_matched IS NULL
            RETURN count(r) AS cnt
            """
        )
        null_count = null_count_result.single()["cnt"]
        if null_count > 0:
            log.error(
                "VALIDATION FAILED: %d HAS_ANALOGUE relationships have null required properties",
                null_count,
            )
            raise RuntimeError(f"Validation failed: {null_count} relationships missing properties")
        else:
            log.info("Validation passed: all HAS_ANALOGUE relationships have required properties")

        # Total count
        total_result = session.run("MATCH ()-[r:HAS_ANALOGUE]->() RETURN count(r) AS cnt")
        total_count = total_result.single()["cnt"]
        log.info("Total HAS_ANALOGUE relationships in Neo4j: %d", total_count)

    unique_pairs = len(
        {(p["from_id"], p["to_id"]) for p in [(p["from_id"], p["to_id"]) for p in pairs]}
    )
    regime_ids = {p["from_id"] for p in pairs}
    print(
        f"\nCreated {total_count} HAS_ANALOGUE relationships across {unique_pairs} directed pairs "
        f"({len(regime_ids)} source regimes)"
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():
    load_dotenv()

    neo4j_uri = os.getenv("NEO4J_URI", "bolt://neo4j:7687")
    neo4j_password = os.getenv("NEO4J_PASSWORD")
    gemini_api_key = os.getenv("GEMINI_API_KEY")

    if not neo4j_password:
        log.error("NEO4J_PASSWORD environment variable is required")
        raise SystemExit(1)

    if not gemini_api_key:
        log.warning(
            "GEMINI_API_KEY not set — narratives will be empty strings (re-run with key to populate)"
        )

    # Step 1: Load regime data
    log.info("Step 1: Loading regime data from %s", REGIME_DATA_PATH)
    all_regimes, complete_regimes, feature_matrix = load_regimes(REGIME_DATA_PATH)

    # Build lookup for all regimes (needed for narrative prompts)
    regime_lookup = {r["id"]: r for r in all_regimes}

    # Step 2: Compute similarity
    log.info("Step 2: Computing normalized pairwise cosine similarity")
    sim_matrix = compute_similarity(feature_matrix)

    # Step 3: Select top analogues
    log.info(
        "Step 3: Selecting top %d analogues per regime (threshold=%.2f)",
        TOP_N_ANALOGUES,
        SIMILARITY_THRESHOLD,
    )
    pairs = select_analogues(complete_regimes, sim_matrix, SIMILARITY_THRESHOLD, TOP_N_ANALOGUES)

    # Step 4: Generate narratives
    log.info("Step 4: Generating narratives via Gemini API (with caching)")
    narrative_cache = load_narrative_cache(NARRATIVE_CACHE_PATH)
    pairs, narrative_cache = generate_narratives(
        pairs, regime_lookup, narrative_cache, gemini_api_key
    )

    # Step 5: MERGE into Neo4j
    log.info("Step 5: Connecting to Neo4j at %s", neo4j_uri)
    driver = GraphDatabase.driver(neo4j_uri, auth=("neo4j", neo4j_password))
    try:
        driver.verify_connectivity()
        log.info("Neo4j connection verified")

        log.info("Step 5: MERGing HAS_ANALOGUE relationships")
        merge_analogues(driver, pairs)

        # Step 6: Validate
        log.info("Step 6: Validating relationships after write")
        validate_relationships(driver, pairs)

    finally:
        driver.close()


if __name__ == "__main__":
    main()
