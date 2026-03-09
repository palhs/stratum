#!/usr/bin/env python3
"""
seed-qdrant-earnings-docs.py — Populate Qdrant earnings_docs with VN30 financial data.
Phase 4 | Plan 04 | Requirement: DATA-04

Usage:
    python scripts/seed-qdrant-earnings-docs.py

Fetches structured financial statements (income statement, balance sheet, cash flow,
ratios) for all VN30 tickers via vnstock API, serializes to English text, chunks,
embeds with FastEmbed, and upserts to Qdrant earnings_docs collection.

Requires: earnings_docs_v1 collection must exist (created by init-qdrant.sh).
Idempotent: deterministic UUIDs ensure re-runs overwrite existing points.

Data source: vnstock VCI API — no manual PDF downloads needed.
All financial data fetched in English (lang='en') for optimal embedding quality
with BAAI/bge-small-en-v1.5.
"""

import logging
import os
import sys
import time
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

if not QDRANT_API_KEY:
    logger.error("QDRANT_API_KEY is not set. Cannot connect to Qdrant.")
    sys.exit(1)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
COLLECTION_NAME = "earnings_docs_v1"
COLLECTION_ALIAS = "earnings_docs"
EMBEDDING_MODEL = "BAAI/bge-small-en-v1.5"
BATCH_SIZE = 64
CHUNK_SIZE = 2048     # ~512 tokens
CHUNK_OVERLAP = 256   # ~12% overlap
API_DELAY = 1.0       # seconds between vnstock API calls to respect rate limits


# ---------------------------------------------------------------------------
# Deterministic UUID for idempotent upsert
# ---------------------------------------------------------------------------
NAMESPACE_EARNINGS = uuid.UUID("e4a5b6c7-d8e9-4f01-a234-567890abcdef")


def make_point_id(doc_id: str, chunk_index: int) -> str:
    """Generate a deterministic UUID5 from doc_id + chunk_index."""
    key = f"{doc_id}:{chunk_index}"
    return str(uuid.uuid5(NAMESPACE_EARNINGS, key))


# ---------------------------------------------------------------------------
# VN30 ticker list via vnstock
# ---------------------------------------------------------------------------

def get_vn30_tickers() -> list[str]:
    """Fetch current VN30 constituent tickers from vnstock."""
    from vnstock import Listing
    symbols_df = Listing(source="vci").symbols_by_group(group="VN30")
    if isinstance(symbols_df, pd.DataFrame):
        for col in ("symbol", "ticker", "code"):
            if col in symbols_df.columns:
                return sorted(symbols_df[col].tolist())
        return sorted(symbols_df.iloc[:, 0].tolist())
    return sorted(list(symbols_df))


# ---------------------------------------------------------------------------
# Financial data fetching
# ---------------------------------------------------------------------------

STATEMENT_TYPES = [
    ("income_statement", "Income Statement"),
    ("balance_sheet", "Balance Sheet"),
    ("cash_flow", "Cash Flow Statement"),
    ("ratio", "Financial Ratios"),
]


def fetch_financials(ticker: str) -> list[dict]:
    """Fetch all financial statement types for a ticker.

    Returns a list of dicts, each with keys:
        ticker, company_name, statement_type, period, fiscal_year, text
    """
    from vnstock import Vnstock

    stock = Vnstock().stock(symbol=ticker, source="VCI")
    results = []

    for attr_name, display_name in STATEMENT_TYPES:
        for period in ("year", "quarter"):
            try:
                method = getattr(stock.finance, attr_name)
                df = method(period=period, lang="en", dropna=True)
                time.sleep(API_DELAY)

                if df is None or df.empty:
                    logger.info("  [%s] %s (%s): no data", ticker, display_name, period)
                    continue

                text = dataframe_to_text(ticker, display_name, period, df)
                if not text or len(text.strip()) < 50:
                    continue

                doc_id = f"{ticker.lower()}_{attr_name}_{period}"
                results.append({
                    "doc_id": doc_id,
                    "ticker": ticker,
                    "statement_type": attr_name,
                    "statement_display": display_name,
                    "period": period,
                    "text": text,
                })
                logger.info(
                    "  [%s] %s (%s): %d chars",
                    ticker, display_name, period, len(text),
                )

            except Exception as exc:
                logger.warning(
                    "  [%s] %s (%s) failed: %s",
                    ticker, display_name, period, exc,
                )
                time.sleep(API_DELAY)

    return results


def dataframe_to_text(
    ticker: str,
    statement_name: str,
    period: str,
    df: pd.DataFrame,
) -> str:
    """Serialize a financial statement DataFrame to readable English text.

    Produces a structured text representation suitable for embedding:
    - Header with ticker, statement type, period
    - Each row as "metric: value1 | value2 | ..." across time periods
    """
    period_label = "Annual" if period == "year" else "Quarterly"
    lines = [
        f"{ticker} — {statement_name} ({period_label})",
        "=" * 60,
        "",
    ]

    # Try to identify the index/metric column vs numeric columns
    # vnstock returns DataFrames where the first column is often the metric name
    cols = df.columns.tolist()

    # If there's a string-type column, use it as the row label
    label_col = None
    for col in cols:
        if df[col].dtype == object:
            label_col = col
            break

    if label_col:
        value_cols = [c for c in cols if c != label_col]
        # Column headers
        if value_cols:
            lines.append(f"Periods: {' | '.join(str(c) for c in value_cols)}")
            lines.append("-" * 60)

        for _, row in df.iterrows():
            label = str(row[label_col])
            values = " | ".join(_fmt_value(row[c]) for c in value_cols)
            lines.append(f"{label}: {values}")
    else:
        # All numeric — use column names as labels, transpose for readability
        lines.append(df.to_string())

    lines.append("")
    return "\n".join(lines)


def _fmt_value(val) -> str:
    """Format a single cell value for text serialization."""
    if pd.isna(val):
        return "N/A"
    if isinstance(val, float):
        if abs(val) >= 1e9:
            return f"{val/1e9:.2f}B"
        if abs(val) >= 1e6:
            return f"{val/1e6:.2f}M"
        if abs(val) >= 1e3:
            return f"{val/1e3:.1f}K"
        return f"{val:.2f}"
    return str(val)


# ---------------------------------------------------------------------------
# Chunking
# ---------------------------------------------------------------------------

def chunk_text(text: str) -> list[str]:
    """Split text using RecursiveCharacterTextSplitter."""
    from langchain_text_splitters import RecursiveCharacterTextSplitter
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    chunks = splitter.split_text(text)
    return [c for c in chunks if len(c.strip()) > 50]


# ---------------------------------------------------------------------------
# Qdrant helpers
# ---------------------------------------------------------------------------

def get_qdrant_client():
    """Create and return a configured QdrantClient."""
    from qdrant_client import QdrantClient
    return QdrantClient(
        host=QDRANT_HOST,
        port=QDRANT_PORT,
        api_key=QDRANT_API_KEY,
        timeout=60,
    )


def ensure_collection_exists(client) -> None:
    """Create earnings_docs_v1 collection + alias if not already present."""
    from qdrant_client.models import Distance, VectorParams

    existing = {c.name for c in client.get_collections().collections}
    if COLLECTION_NAME not in existing:
        logger.info("Collection '%s' not found — creating now...", COLLECTION_NAME)
        client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=VectorParams(size=384, distance=Distance.COSINE),
        )
        client.update_collection_aliases(
            change_aliases_operations=[
                {
                    "create_alias": {
                        "collection_name": COLLECTION_NAME,
                        "alias_name": COLLECTION_ALIAS,
                    }
                }
            ]
        )
        logger.info("Created collection '%s' with alias '%s'.", COLLECTION_NAME, COLLECTION_ALIAS)
    else:
        logger.info("Collection '%s' already exists.", COLLECTION_NAME)


def upsert_chunks(client, chunks: list[str], payloads: list[dict], embedding_model) -> int:
    """Embed and upsert a batch of text chunks to Qdrant."""
    from qdrant_client.models import PointStruct

    if not chunks:
        return 0

    embeddings = list(embedding_model.embed(chunks, batch_size=BATCH_SIZE))

    points = [
        PointStruct(
            id=payloads[i]["_point_id"],
            vector=embeddings[i].tolist(),
            payload={k: v for k, v in payloads[i].items() if k != "_point_id"},
        )
        for i in range(len(chunks))
    ]

    client.upload_points(
        collection_name=COLLECTION_NAME,
        points=points,
        batch_size=BATCH_SIZE,
        wait=True,
    )
    return len(points)


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def validate_uploads(client, processed_tickers: list[str]) -> None:
    """Run post-upsert validation with similarity search per ticker."""
    collection_info = client.get_collection(COLLECTION_NAME)
    total_points = collection_info.points_count
    logger.info("Collection '%s' total points: %d", COLLECTION_NAME, total_points)

    if not processed_tickers:
        logger.info("No tickers processed — skipping similarity validation.")
        return

    from fastembed import TextEmbedding
    model = TextEmbedding(model_name=EMBEDDING_MODEL)

    for ticker in processed_tickers[:5]:
        query_text = f"{ticker} revenue net income"
        query_vec = list(model.embed([query_text], batch_size=1))[0].tolist()
        results = client.search(
            collection_name=COLLECTION_NAME,
            query_vector=query_vec,
            limit=1,
            with_payload=["ticker", "statement_type", "period"],
        )
        if results:
            top = results[0]
            logger.info(
                "  Validation [%s]: ticker=%s type=%s period=%s score=%.4f",
                ticker,
                top.payload.get("ticker"),
                top.payload.get("statement_type"),
                top.payload.get("period"),
                top.score,
            )
        else:
            logger.warning("  Validation [%s]: no results.", ticker)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    logger.info("=================================================")
    logger.info("Stratum — Qdrant earnings_docs Seed Script")
    logger.info("Phase 4 | Plan 04 | Requirement: DATA-04")
    logger.info("Data source: vnstock VCI API (structured financials)")
    logger.info("=================================================")

    # ------------------------------------------------------------------
    # 1. Fetch VN30 tickers
    # ------------------------------------------------------------------
    logger.info("Fetching VN30 constituent tickers...")
    tickers = get_vn30_tickers()
    logger.info("VN30 tickers (%d): %s", len(tickers), ", ".join(tickers))

    # ------------------------------------------------------------------
    # 2. Initialize Qdrant client and ensure collection exists
    # ------------------------------------------------------------------
    logger.info("Connecting to Qdrant at %s:%d ...", QDRANT_HOST, QDRANT_PORT)
    client = get_qdrant_client()
    ensure_collection_exists(client)

    # ------------------------------------------------------------------
    # 3. Initialize FastEmbed model
    # ------------------------------------------------------------------
    logger.info("Loading FastEmbed model: %s ...", EMBEDDING_MODEL)
    from fastembed import TextEmbedding
    embedding_model = TextEmbedding(model_name=EMBEDDING_MODEL)
    logger.info("Model loaded.")

    # ------------------------------------------------------------------
    # 4. Fetch and process each ticker
    # ------------------------------------------------------------------
    total_chunks_uploaded = 0
    total_docs_processed = 0
    total_docs_failed = 0
    processed_tickers: list[str] = []

    for i, ticker in enumerate(tickers, 1):
        logger.info("--- [%d/%d] Ticker: %s ---", i, len(tickers), ticker)

        try:
            docs = fetch_financials(ticker)
        except Exception as exc:
            logger.error("  [%s] Failed to fetch financials: %s", ticker, exc)
            total_docs_failed += 1
            continue

        if not docs:
            logger.warning("  [%s] No financial data retrieved — skipping.", ticker)
            total_docs_failed += 1
            continue

        ticker_chunks: list[str] = []
        ticker_payloads: list[dict] = []

        for doc in docs:
            chunks = chunk_text(doc["text"])
            if not chunks:
                continue

            total_chunks = len(chunks)
            for chunk_index, chunk_text_content in enumerate(chunks):
                ticker_chunks.append(chunk_text_content)
                ticker_payloads.append({
                    "_point_id": make_point_id(doc["doc_id"], chunk_index),
                    "text": chunk_text_content,
                    "ticker": doc["ticker"],
                    "statement_type": doc["statement_type"],
                    "statement_display": doc["statement_display"],
                    "period": doc["period"],
                    "doc_id": doc["doc_id"],
                    "lang": "en",
                    "chunk_index": chunk_index,
                    "total_chunks": total_chunks,
                })

            total_docs_processed += 1

        if ticker_chunks:
            uploaded = upsert_chunks(client, ticker_chunks, ticker_payloads, embedding_model)
            total_chunks_uploaded += uploaded
            processed_tickers.append(ticker)
            logger.info("  Uploaded %d chunks for %s.", uploaded, ticker)

    # ------------------------------------------------------------------
    # 5. Validate
    # ------------------------------------------------------------------
    logger.info("=================================================")
    logger.info("Running post-upsert validation...")
    validate_uploads(client, processed_tickers)

    # ------------------------------------------------------------------
    # 6. Summary
    # ------------------------------------------------------------------
    logger.info("=================================================")
    logger.info(
        "Summary: Uploaded %d chunks from %d statement fetches (%d tickers) to %s",
        total_chunks_uploaded,
        total_docs_processed,
        len(processed_tickers),
        COLLECTION_ALIAS,
    )
    if total_docs_failed > 0:
        logger.warning(
            "%d ticker(s) failed or returned no data.",
            total_docs_failed,
        )
    logger.info("=================================================")
    logger.info("DONE. earnings_docs collection is ready for retrieval.")
    logger.info("=================================================")


if __name__ == "__main__":
    main()
