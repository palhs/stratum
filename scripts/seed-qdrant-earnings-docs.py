#!/usr/bin/env python3
"""
seed-qdrant-earnings-docs.py — Populate Qdrant earnings_docs with VN30 financial data.
Phase 4 | Plan 04 | Requirement: DATA-04

Usage:
    python scripts/seed-qdrant-earnings-docs.py

Architecture: Spawns a subprocess per ticker to avoid OOM from vnstock/onnxruntime
memory leaks (~300MB/ticker that gc cannot reclaim). Each subprocess imports vnstock,
fetches data, embeds, upserts, and exits — OS reclaims all memory.

Requires: earnings_docs_v1 collection must exist (created by init-qdrant.sh).
Idempotent: deterministic UUIDs ensure re-runs overwrite existing points.

Data source: vnstock VCI API — no manual PDF downloads needed.
"""

import json
import logging
import os
import subprocess
import sys
import uuid

import pandas as pd
from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Load environment
# ---------------------------------------------------------------------------
load_dotenv()

QDRANT_HOST = os.environ.get("QDRANT_HOST", "qdrant")
QDRANT_PORT = int(os.environ.get("QDRANT_PORT", "6333"))
QDRANT_API_KEY = os.environ.get("QDRANT_API_KEY", "")
QDRANT_HTTPS = os.environ.get("QDRANT_HTTPS", "false").lower() in ("true", "1", "yes")

if not QDRANT_API_KEY:
    logger.error("QDRANT_API_KEY is not set. Cannot connect to Qdrant.")
    sys.exit(1)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
COLLECTION_NAME = "earnings_docs_v1"
EMBEDDING_MODEL = "BAAI/bge-small-en-v1.5"
BATCH_SIZE = 16
CHUNK_SIZE = 2048
CHUNK_OVERLAP = 256
API_DELAY = 1.0

NAMESPACE_EARNINGS = uuid.UUID("e4a5b6c7-d8e9-4f01-a234-567890abcdef")

STATEMENT_TYPES = [
    ("income_statement", "Income Statement"),
    ("balance_sheet", "Balance Sheet"),
    ("cash_flow", "Cash Flow Statement"),
    ("ratio", "Financial Ratios"),
]


# ---------------------------------------------------------------------------
# Shared helpers (used by both orchestrator and worker)
# ---------------------------------------------------------------------------


def make_point_id(doc_id: str, chunk_index: int) -> str:
    key = f"{doc_id}:{chunk_index}"
    return str(uuid.uuid5(NAMESPACE_EARNINGS, key))


def _fmt_value(val) -> str:
    try:
        if pd.isna(val):
            return "N/A"
    except (ValueError, TypeError):
        pass
    if isinstance(val, float):
        if abs(val) >= 1e9:
            return f"{val/1e9:.2f}B"
        if abs(val) >= 1e6:
            return f"{val/1e6:.2f}M"
        if abs(val) >= 1e3:
            return f"{val/1e3:.1f}K"
        return f"{val:.2f}"
    return str(val)


# ===========================================================================
# WORKER MODE: process a single ticker (runs in subprocess)
# ===========================================================================


def worker_main(ticker: str) -> None:
    """Process one ticker: fetch, chunk, embed, upsert. Called in subprocess."""
    import gc
    import time
    from fastembed import TextEmbedding, SparseTextEmbedding
    from langchain_text_splitters import RecursiveCharacterTextSplitter
    from qdrant_client import QdrantClient
    from qdrant_client.models import PointStruct, SparseVector

    logger.info("  Worker started for %s (PID %d)", ticker, os.getpid())

    # Connect to Qdrant
    client = QdrantClient(
        host=QDRANT_HOST, port=QDRANT_PORT, api_key=QDRANT_API_KEY,
        https=QDRANT_HTTPS, timeout=60,
    )

    # Load embedding models — dense (BAAI/bge-small-en-v1.5) + sparse BM25
    embedding_model = TextEmbedding(model_name=EMBEDDING_MODEL)
    sparse_model = SparseTextEmbedding(model_name="Qdrant/bm25")

    # Fetch financial data
    from vnstock import Vnstock
    stock = Vnstock().stock(symbol=ticker, source="VCI")

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP,
        separators=["\n\n", "\n", ". ", " ", ""],
    )

    total_uploaded = 0
    total_statements = 0

    for attr_name, display_name in STATEMENT_TYPES:
        for period in ("year", "quarter"):
            try:
                method = getattr(stock.finance, attr_name)
                df = method(period=period, lang="en", dropna=True)
                time.sleep(API_DELAY)

                if df is None or (isinstance(df, pd.DataFrame) and df.empty):
                    continue

                # Serialize DataFrame to text
                text = dataframe_to_text(ticker, display_name, period, df)
                del df
                if not text or len(text.strip()) < 50:
                    continue

                logger.info("  [%s] %s (%s): %d chars", ticker, display_name, period, len(text))

                # Chunk
                chunks = [c for c in splitter.split_text(text) if len(c.strip()) > 50]
                del text
                if not chunks:
                    continue

                doc_id = f"{ticker.lower()}_{attr_name}_{period}"
                total_chunks = len(chunks)

                # Embed and upsert in small batches — named vectors for hybrid search
                for batch_start in range(0, len(chunks), BATCH_SIZE):
                    batch_texts = chunks[batch_start:batch_start + BATCH_SIZE]
                    dense_embeddings = list(embedding_model.embed(batch_texts, batch_size=BATCH_SIZE))
                    sparse_embeddings = list(sparse_model.embed(batch_texts, batch_size=BATCH_SIZE))

                    points = [
                        PointStruct(
                            id=make_point_id(doc_id, batch_start + j),
                            vector={
                                "text-dense": dense_embeddings[j].tolist(),
                                "text-sparse": SparseVector(
                                    indices=sparse_embeddings[j].indices.tolist(),
                                    values=sparse_embeddings[j].values.tolist(),
                                ),
                            },
                            payload={
                                "text": batch_texts[j],
                                "ticker": ticker,
                                "statement_type": attr_name,
                                "statement_display": display_name,
                                "period": period,
                                "doc_id": doc_id,
                                "lang": "en",
                                "chunk_index": batch_start + j,
                                "total_chunks": total_chunks,
                            },
                        )
                        for j in range(len(batch_texts))
                    ]

                    client.upload_points(
                        collection_name=COLLECTION_NAME,
                        points=points,
                        batch_size=BATCH_SIZE,
                        wait=True,
                    )
                    total_uploaded += len(points)
                    del dense_embeddings, sparse_embeddings, points

                del chunks
                gc.collect()
                total_statements += 1

            except SystemExit as exc:
                logger.warning("  [%s] %s (%s): vnstock rate limit — pausing 60s", ticker, display_name, period)
                time.sleep(60)
            except Exception as exc:
                logger.warning("  [%s] %s (%s) failed: %s", ticker, display_name, period, exc)
                time.sleep(API_DELAY)

    # Output result as JSON for the orchestrator to parse
    result = {"ticker": ticker, "chunks": total_uploaded, "statements": total_statements}
    print(f"__RESULT__:{json.dumps(result)}")


def dataframe_to_text(ticker: str, statement_name: str, period: str, df: pd.DataFrame) -> str:
    period_label = "Annual" if period == "year" else "Quarterly"
    lines = [f"{ticker} — {statement_name} ({period_label})", "=" * 60, ""]

    cols = df.columns.tolist()
    label_col = None
    for col in cols:
        if df[col].dtype == object:
            label_col = col
            break

    if label_col:
        value_cols = [c for c in cols if c != label_col]
        if value_cols:
            lines.append(f"Periods: {' | '.join(str(c) for c in value_cols)}")
            lines.append("-" * 60)
        for _, row in df.iterrows():
            label = str(row[label_col])
            values = " | ".join(_fmt_value(row[c]) for c in value_cols)
            lines.append(f"{label}: {values}")
    else:
        lines.append(df.to_string())

    lines.append("")
    return "\n".join(lines)


# ===========================================================================
# ORCHESTRATOR MODE: coordinate per-ticker subprocesses
# ===========================================================================


def get_vn30_tickers() -> list[str]:
    from vnstock import Listing
    try:
        symbols_df = Listing(source="vci").symbols_by_group(group="VN30")
    except SystemExit as exc:
        raise RuntimeError("Cannot fetch VN30 tickers — vnstock rate limited") from exc

    if isinstance(symbols_df, pd.DataFrame):
        if symbols_df.empty:
            raise RuntimeError("VN30 ticker list is empty")
        for col in ("symbol", "ticker", "code"):
            if col in symbols_df.columns:
                return sorted(symbols_df[col].tolist())
        return sorted(symbols_df.iloc[:, 0].tolist())
    if isinstance(symbols_df, pd.Series):
        if symbols_df.empty:
            raise RuntimeError("VN30 ticker list is empty")
        return sorted(symbols_df.tolist())
    result = list(symbols_df) if symbols_df is not None else []
    if not result:
        raise RuntimeError("VN30 ticker list is empty")
    return sorted(result)


def ensure_collection_exists() -> None:
    from qdrant_client import QdrantClient
    client = QdrantClient(
        host=QDRANT_HOST, port=QDRANT_PORT, api_key=QDRANT_API_KEY,
        https=QDRANT_HTTPS, timeout=60,
    )
    existing = {c.name for c in client.get_collections().collections}
    if COLLECTION_NAME not in existing:
        raise RuntimeError(
            f"Collection '{COLLECTION_NAME}' does not exist. "
            "Run: docker compose --profile storage run --rm qdrant-init"
        )
    logger.info("Collection '%s' confirmed present.", COLLECTION_NAME)


def run_ticker_subprocess(ticker: str, index: int, total: int) -> dict:
    """Spawn a subprocess to process one ticker. Returns result dict."""
    logger.info("--- [%d/%d] Ticker: %s ---", index, total, ticker)

    result = subprocess.run(
        [sys.executable, __file__, "--worker", ticker],
        capture_output=True,
        text=True,
        timeout=600,  # 10 min max per ticker
    )

    # Stream worker logs to our logger
    for line in result.stdout.splitlines():
        if line.startswith("__RESULT__:"):
            return json.loads(line[len("__RESULT__:"):])
        else:
            print(line)

    for line in result.stderr.splitlines():
        print(line, file=sys.stderr)

    if result.returncode != 0:
        # Exit code -9 = OOM kill; worker uploaded data before being killed
        if result.returncode == -9:
            logger.warning("  [%s] Worker OOM-killed (code -9) — partial data uploaded", ticker)
            return {"ticker": ticker, "chunks": 0, "statements": 0, "partial": True}
        logger.error("  [%s] Worker exited with code %d", ticker, result.returncode)
        return {"ticker": ticker, "chunks": 0, "statements": 0, "error": True}

    # No result line found
    return {"ticker": ticker, "chunks": 0, "statements": 0}


def validate_uploads(processed_tickers: list[str]) -> None:
    from qdrant_client import QdrantClient
    from qdrant_client.models import Filter, FieldCondition, MatchValue

    client = QdrantClient(
        host=QDRANT_HOST, port=QDRANT_PORT, api_key=QDRANT_API_KEY,
        https=QDRANT_HTTPS, timeout=60,
    )

    info = client.get_collection(COLLECTION_NAME)
    logger.info("Collection '%s' total points: %d", COLLECTION_NAME, info.points_count)

    if not processed_tickers:
        return

    # Validate by counting points per ticker (no embedding model needed)
    for ticker in processed_tickers[:5]:
        count = client.count(
            collection_name=COLLECTION_NAME,
            count_filter=Filter(
                must=[FieldCondition(key="ticker", match=MatchValue(value=ticker))]
            ),
            exact=True,
        )
        logger.info("  Validation [%s]: %d points found", ticker, count.count)


def main() -> None:
    logger.info("=================================================")
    logger.info("Stratum — Qdrant earnings_docs Seed Script")
    logger.info("Phase 4 | Plan 04 | Requirement: DATA-04")
    logger.info("Subprocess-per-ticker architecture for memory safety")
    logger.info("=================================================")

    # 1. Determine tickers
    # --tickers DGC,FPT,GAS  → process only these, preserve existing data
    ticker_arg = None
    for i, arg in enumerate(sys.argv[1:], 1):
        if arg == "--tickers" and i < len(sys.argv) - 1:
            ticker_arg = sys.argv[i + 1]
            break
        if arg.startswith("--tickers="):
            ticker_arg = arg.split("=", 1)[1]
            break

    if ticker_arg:
        tickers = sorted([t.strip().upper() for t in ticker_arg.split(",") if t.strip()])
        logger.info("Selective mode: processing %d tickers: %s", len(tickers), ", ".join(tickers))
    else:
        logger.info("Fetching VN30 constituent tickers...")
        tickers = get_vn30_tickers()
        logger.info("VN30 tickers (%d): %s", len(tickers), ", ".join(tickers))

    # 2. Verify collection; only clear if processing all tickers
    ensure_collection_exists()
    if not ticker_arg:
        from qdrant_client import QdrantClient
        client = QdrantClient(
            host=QDRANT_HOST, port=QDRANT_PORT, api_key=QDRANT_API_KEY,
            https=QDRANT_HTTPS, timeout=60,
        )
        info = client.get_collection(COLLECTION_NAME)
        if info.points_count > 0:
            logger.info("Clearing %d existing points from '%s'...", info.points_count, COLLECTION_NAME)
            from qdrant_client.models import FilterSelector, Filter
            client.delete(
                collection_name=COLLECTION_NAME,
                points_selector=FilterSelector(filter=Filter()),
            )
            logger.info("Collection cleared.")
        del client
    else:
        logger.info("Selective mode — skipping collection clear (preserving existing data).")

    # 3. Process each ticker in its own subprocess
    total_chunks = 0
    total_statements = 0
    processed_tickers = []
    partial_tickers = []
    failed_tickers = []

    for i, ticker in enumerate(tickers, 1):
        try:
            result = run_ticker_subprocess(ticker, i, len(tickers))
        except subprocess.TimeoutExpired:
            logger.error("  [%s] Subprocess timed out after 600s", ticker)
            failed_tickers.append(ticker)
            continue
        except Exception as exc:
            logger.error("  [%s] Subprocess error: %s", ticker, exc)
            failed_tickers.append(ticker)
            continue

        if result.get("error"):
            failed_tickers.append(ticker)
        elif result.get("partial"):
            # OOM-killed but uploaded data before dying
            partial_tickers.append(ticker)
            logger.info("  [%s] Partial upload (OOM-killed mid-process).", ticker)
        elif result["chunks"] > 0:
            total_chunks += result["chunks"]
            total_statements += result["statements"]
            processed_tickers.append(ticker)
            logger.info("  Uploaded %d chunks for %s.", result["chunks"], ticker)
        else:
            logger.warning("  [%s] No data retrieved.", ticker)
            failed_tickers.append(ticker)

    # 4. Validate — include partial tickers since they uploaded data too
    all_with_data = processed_tickers + partial_tickers
    logger.info("=================================================")
    logger.info("Running post-upsert validation...")
    validate_uploads(all_with_data)

    # 5. Summary
    logger.info("=================================================")
    logger.info(
        "Summary: %d tickers fully completed, %d partial (OOM), %d failed",
        len(processed_tickers), len(partial_tickers), len(failed_tickers),
    )
    if partial_tickers:
        logger.info("Partial tickers (data uploaded before OOM): %s", ", ".join(partial_tickers))
    if failed_tickers:
        logger.warning("Failed tickers: %s", ", ".join(failed_tickers))
    logger.info("=================================================")
    logger.info("DONE. earnings_docs collection is ready for retrieval.")
    logger.info("=================================================")


# ===========================================================================
# Entry point: --worker <TICKER> for subprocess mode, otherwise orchestrator
# ===========================================================================

if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] == "--worker":
        worker_main(sys.argv[2])
    else:
        main()
