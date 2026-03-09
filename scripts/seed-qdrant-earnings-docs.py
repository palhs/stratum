#!/usr/bin/env python3
"""
seed-qdrant-earnings-docs.py — Populate Qdrant earnings_docs with VN30 company reports.
Phase 4 | Plan 04 | Requirement: DATA-04

Usage:
    python scripts/seed-qdrant-earnings-docs.py

Reads VN30 company annual reports and quarterly statements from data/earnings/{ticker}/,
chunks, embeds with FastEmbed, and upserts to Qdrant earnings_docs collection.

Requires: earnings_docs_v1 collection must exist (created by init-qdrant.sh).
Documents must be manually placed in data/earnings/{ticker}/ directories.
Idempotent: deterministic UUIDs ensure re-runs overwrite existing points.

NOTE: Vietnamese companies do NOT have earnings call transcripts (no earnings calls
on HOSE). The equivalent documents are annual reports (bao cao thuong nien) and
quarterly financial statements (bao cao tai chinh quy) from hsx.vn disclosure portal.

WARNING: BAAI/bge-small-en-v1.5 is an English-only model. Vietnamese-language documents
(lang='vi') will produce degraded embeddings. Prioritize English versions where available.
Large VN30 companies (VCB, BID, CTG, VIC, VHM, HPG, MWG, FPT, VNM, MSN, GAS, PLX)
publish English annual reports for international investor relations.
"""

import json
import logging
import os
import sys
import uuid
from pathlib import Path
from typing import Optional

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
CHUNK_SIZE = 2048     # ~512 tokens (4 chars/token approx)
CHUNK_OVERLAP = 256   # ~12% overlap

# Path resolution — script can be run from any directory
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
MANIFEST_PATH = PROJECT_ROOT / "data" / "earnings" / "manifest.json"
EARNINGS_DATA_DIR = PROJECT_ROOT / "data" / "earnings"


# ---------------------------------------------------------------------------
# Deterministic UUID for idempotent upsert
# ---------------------------------------------------------------------------
NAMESPACE_EARNINGS = uuid.UUID("e4a5b6c7-d8e9-4f01-a234-567890abcdef")


def make_point_id(doc_id: str, chunk_index: int) -> str:
    """Generate a deterministic UUID5 from doc_id + chunk_index.

    Re-running the script with the same document produces the same UUIDs,
    which causes Qdrant to overwrite (upsert) existing points rather than
    creating duplicates. This ensures idempotency.
    """
    key = f"{doc_id}:{chunk_index}"
    return str(uuid.uuid5(NAMESPACE_EARNINGS, key))


# ---------------------------------------------------------------------------
# Text extraction helpers
# ---------------------------------------------------------------------------

def extract_text_from_pdf(pdf_path: Path) -> Optional[str]:
    """Extract text from a PDF file using pdfplumber.

    Returns extracted text joined across pages, or None on failure.
    """
    try:
        import pdfplumber
        with pdfplumber.open(str(pdf_path)) as pdf:
            pages_text = []
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    pages_text.append(page_text)
            if not pages_text:
                logger.warning("  PDF extracted no text: %s", pdf_path.name)
                return None
            return "\n\n".join(pages_text)
    except Exception as exc:
        logger.warning("  PDF extraction failed for %s: %s", pdf_path.name, exc)
        return None


def extract_text_from_txt(txt_path: Path) -> Optional[str]:
    """Read text content from a plain text file.

    Returns text content, or None on failure.
    """
    try:
        return txt_path.read_text(encoding="utf-8", errors="replace")
    except Exception as exc:
        logger.warning("  Text file read failed for %s: %s", txt_path.name, exc)
        return None


def extract_text_from_file(file_path: Path) -> Optional[str]:
    """Dispatch text extraction based on file extension.

    Supports: .pdf, .txt
    Returns None if unsupported format or extraction fails.
    """
    suffix = file_path.suffix.lower()
    if suffix == ".pdf":
        return extract_text_from_pdf(file_path)
    elif suffix == ".txt":
        return extract_text_from_txt(file_path)
    else:
        logger.warning("  Unsupported file format: %s (skipping)", file_path.name)
        return None


# ---------------------------------------------------------------------------
# Chunking
# ---------------------------------------------------------------------------

def chunk_text(text: str) -> list[str]:
    """Split text using RecursiveCharacterTextSplitter.

    Settings match seed-qdrant-macro-docs.py for cross-collection consistency:
    - chunk_size=2048 characters (~512 tokens for bge-small-en-v1.5)
    - chunk_overlap=256 characters (~12% overlap, preserves cross-boundary context)
    - separators prioritize semantic boundaries before character-level splits
    """
    from langchain_text_splitters import RecursiveCharacterTextSplitter
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    chunks = splitter.split_text(text)
    # Filter out very short chunks that are unlikely to carry useful information
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
    """Create earnings_docs_v1 collection + alias if not already present.

    The collection should exist after init-qdrant.sh runs. This function
    creates it as a fallback if the seed script is run standalone.
    """
    from qdrant_client.models import Distance, VectorParams

    existing = {c.name for c in client.get_collections().collections}
    if COLLECTION_NAME not in existing:
        logger.info("Collection '%s' not found — creating now...", COLLECTION_NAME)
        client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=VectorParams(size=384, distance=Distance.COSINE),
        )
        # Create stable alias so retrieval code can use 'earnings_docs'
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
        logger.info("Collection '%s' already exists — skipping creation.", COLLECTION_NAME)


def upsert_chunks(client, chunks: list[str], payloads: list[dict], embedding_model) -> int:
    """Embed and upsert a batch of text chunks to Qdrant.

    Uses upload_points() which handles internal batching, retry logic,
    and parallel upload automatically.

    Returns the number of points uploaded.
    """
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
    """Run post-upsert validation.

    1. Log total point count in collection.
    2. For each processed ticker, run a similarity search and log top result.
    """
    collection_info = client.get_collection(COLLECTION_NAME)
    total_points = collection_info.points_count
    logger.info("Collection '%s' total points: %d", COLLECTION_NAME, total_points)

    if not processed_tickers:
        logger.info("No tickers were processed — skipping similarity validation.")
        return

    from fastembed import TextEmbedding
    model = TextEmbedding(model_name=EMBEDDING_MODEL)

    for ticker in processed_tickers[:5]:  # Validate up to 5 tickers to keep it fast
        query_text = ticker
        query_vec = list(model.embed([query_text], batch_size=1))[0].tolist()
        results = client.search(
            collection_name=COLLECTION_NAME,
            query_vector=query_vec,
            limit=1,
            with_payload=["ticker", "company_name", "fiscal_period", "doc_type"],
        )
        if results:
            top = results[0]
            logger.info(
                "  Validation [%s]: top result ticker=%s period=%s score=%.4f",
                ticker,
                top.payload.get("ticker"),
                top.payload.get("fiscal_period"),
                top.score,
            )
        else:
            logger.warning("  Validation [%s]: no results returned from similarity search.", ticker)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    logger.info("=================================================")
    logger.info("Stratum — Qdrant earnings_docs Seed Script")
    logger.info("Phase 4 | Plan 04 | Requirement: DATA-04")
    logger.info("=================================================")

    # ------------------------------------------------------------------
    # 1. Load manifest
    # ------------------------------------------------------------------
    if not MANIFEST_PATH.exists():
        logger.error("Manifest not found at %s", MANIFEST_PATH)
        sys.exit(1)

    with open(MANIFEST_PATH, encoding="utf-8") as f:
        manifest = json.load(f)

    total_entries = len(manifest)
    skipped_no_file = [e for e in manifest if e.get("filename") is None]
    to_process = [e for e in manifest if e.get("filename") is not None]

    logger.info(
        "Manifest: %d total entries | %d to process | %d skipped (no filename set)",
        total_entries,
        len(to_process),
        len(skipped_no_file),
    )

    if not to_process:
        logger.warning(
            "No documents to process — all manifest entries have filename=null."
        )
        logger.warning(
            "Download documents from hsx.vn and update manifest filename fields,"
        )
        logger.warning(
            "then place files in data/earnings/{TICKER}/ and re-run this script."
        )
        logger.info("Proceeding to initialize Qdrant collection (no points will be uploaded).")

    # Group to_process by ticker for progress reporting
    by_ticker: dict[str, list] = {}
    for entry in to_process:
        by_ticker.setdefault(entry["ticker"], []).append(entry)

    if by_ticker:
        logger.info("Processing %d documents for %d tickers.", len(to_process), len(by_ticker))

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
    # 4. Process documents ticker by ticker
    # ------------------------------------------------------------------
    total_chunks_uploaded = 0
    total_docs_processed = 0
    total_docs_failed = 0
    processed_tickers: list[str] = []

    for ticker, entries in by_ticker.items():
        logger.info("--- Ticker: %s (%d documents) ---", ticker, len(entries))
        ticker_dir = EARNINGS_DATA_DIR / ticker

        if not ticker_dir.exists():
            logger.warning(
                "  Directory %s does not exist — skipping all %d entries for %s.",
                ticker_dir,
                len(entries),
                ticker,
            )
            total_docs_failed += len(entries)
            continue

        ticker_chunks: list[str] = []
        ticker_payloads: list[dict] = []

        for entry in entries:
            doc_id = entry["doc_id"]
            filename = entry["filename"]
            lang = entry.get("lang", "vi")
            doc_file = ticker_dir / filename

            if not doc_file.exists():
                logger.warning(
                    "  File not found: %s/%s — skipping %s.",
                    ticker,
                    filename,
                    doc_id,
                )
                total_docs_failed += 1
                continue

            if lang == "vi":
                logger.warning(
                    "  [%s] lang=vi — embedding quality will be degraded with %s (English-only model).",
                    doc_id,
                    EMBEDDING_MODEL,
                )

            # Extract text
            text = extract_text_from_file(doc_file)
            if not text or not text.strip():
                logger.warning("  [%s] No text extracted from %s — skipping.", doc_id, filename)
                total_docs_failed += 1
                continue

            # Chunk text
            chunks = chunk_text(text)
            if not chunks:
                logger.warning("  [%s] Chunking produced 0 usable chunks — skipping.", doc_id)
                total_docs_failed += 1
                continue

            total_chunks = len(chunks)
            logger.info(
                "  [%s] Extracted %d chars -> %d chunks (lang=%s).",
                doc_id,
                len(text),
                total_chunks,
                lang,
            )

            # Build payloads with deterministic point IDs
            for chunk_index, chunk_text_content in enumerate(chunks):
                ticker_chunks.append(chunk_text_content)
                ticker_payloads.append(
                    {
                        "_point_id": make_point_id(doc_id, chunk_index),
                        "text": chunk_text_content,
                        "ticker": entry["ticker"],
                        "company_name": entry["company_name"],
                        "fiscal_period": entry["fiscal_period"],
                        "fiscal_year": entry["fiscal_year"],
                        "doc_type": entry["doc_type"],
                        "doc_id": doc_id,
                        "lang": lang,
                        "chunk_index": chunk_index,
                        "total_chunks": total_chunks,
                    }
                )

            total_docs_processed += 1

        # Upsert all chunks for this ticker in one batch call
        if ticker_chunks:
            uploaded = upsert_chunks(client, ticker_chunks, ticker_payloads, embedding_model)
            total_chunks_uploaded += uploaded
            processed_tickers.append(ticker)
            logger.info(
                "  Uploaded %d chunks for %s.", uploaded, ticker
            )

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
        "Summary: Uploaded %d chunks from %d documents (%d tickers) to %s",
        total_chunks_uploaded,
        total_docs_processed,
        len(processed_tickers),
        COLLECTION_ALIAS,
    )
    if total_docs_failed > 0:
        logger.warning(
            "%d document(s) failed to process (file not found, extraction error, or empty).",
            total_docs_failed,
        )
    if skipped_no_file:
        logger.info(
            "%d manifest entries skipped — filename=null (documents not yet downloaded).",
            len(skipped_no_file),
        )
    logger.info("=================================================")
    logger.info("DONE. earnings_docs collection is ready for Phase 5 retrieval validation.")
    logger.info("=================================================")


if __name__ == "__main__":
    main()
