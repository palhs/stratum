#!/usr/bin/env python3
"""
seed-qdrant-macro-docs.py — Populate Qdrant macro_docs with FOMC + SBV documents.
Phase 4 | Plan 03 | Requirement: DATA-03

Usage:
    python scripts/seed-qdrant-macro-docs.py

Downloads FOMC PDFs from federalreserve.gov, reads SBV PDFs from data/sbv/,
chunks, embeds with FastEmbed, and upserts to Qdrant macro_docs collection.

Requires: macro_docs_v1 collection must exist (created by init-qdrant.sh).
Idempotent: deterministic UUIDs ensure re-runs overwrite existing points.
"""

import json
import logging
import os
import time
import uuid
from pathlib import Path
from typing import Optional

import httpx
import pdfplumber
from dotenv import load_dotenv
from fastembed import TextEmbedding
from langchain_text_splitters import RecursiveCharacterTextSplitter
from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

QDRANT_HOST = os.getenv("QDRANT_HOST", "qdrant")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", "6333"))
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")

if not QDRANT_API_KEY:
    raise EnvironmentError("QDRANT_API_KEY environment variable is required")

COLLECTION_NAME = "macro_docs_v1"
COLLECTION_ALIAS = "macro_docs"
EMBED_MODEL = "BAAI/bge-small-en-v1.5"
EMBED_BATCH_SIZE = 64
UPLOAD_BATCH_SIZE = 64

CHUNK_SIZE = 2048        # ~512 tokens for bge-small-en-v1.5
CHUNK_OVERLAP = 256      # ~12% overlap per RESEARCH.md Pattern 4

# Namespace UUID for deterministic point IDs — fixed for idempotent re-runs
POINT_NAMESPACE = uuid.UUID("8e4b7c6a-2d5f-4e9a-b1c3-0f7e8d2a6b4c")

# Project root relative to this script (scripts/ -> project root)
PROJECT_ROOT = Path(__file__).parent.parent
FOMC_DATA_DIR = PROJECT_ROOT / "data" / "fomc"
SBV_DATA_DIR = PROJECT_ROOT / "data" / "sbv"
FOMC_MANIFEST = FOMC_DATA_DIR / "manifest.json"
SBV_MANIFEST = SBV_DATA_DIR / "manifest.json"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_point_id(doc_id: str, chunk_index: int) -> str:
    """Generate a deterministic UUID for a document chunk using uuid5."""
    name = f"{doc_id}::{chunk_index}"
    return str(uuid.uuid5(POINT_NAMESPACE, name))


def download_fomc_pdf(url: str, dest_path: Path) -> bool:
    """
    Download a FOMC PDF from the Federal Reserve website.
    Returns True on success, False on failure (logs warning, does not raise).
    """
    if dest_path.exists():
        logger.info("Cache hit — skipping download: %s", dest_path.name)
        return True

    logger.info("Downloading %s -> %s", url, dest_path.name)
    try:
        with httpx.Client(follow_redirects=True, timeout=60.0) as client:
            response = client.get(url)
        if response.status_code == 200:
            dest_path.write_bytes(response.content)
            logger.info(
                "Downloaded %s (%.1f KB)", dest_path.name, len(response.content) / 1024
            )
            return True
        else:
            logger.warning(
                "HTTP %d for %s — skipping document", response.status_code, url
            )
            return False
    except httpx.RequestError as exc:
        logger.warning("Request error for %s: %s — skipping", url, exc)
        return False


def extract_text_from_pdf(pdf_path: Path) -> Optional[str]:
    """
    Extract full text from a PDF using pdfplumber.
    Returns None on failure (logs warning, does not raise).
    """
    try:
        pages_text = []
        with pdfplumber.open(pdf_path) as pdf:
            page_count = len(pdf.pages)
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    pages_text.append(text)
        full_text = "\n\n".join(pages_text)
        char_count = len(full_text)
        logger.info(
            "Extracted text from %s — %d pages, %d chars",
            pdf_path.name,
            page_count,
            char_count,
        )
        if char_count == 0:
            logger.warning(
                "Zero characters extracted from %s — may be a scanned image PDF",
                pdf_path.name,
            )
            return None
        return full_text
    except Exception as exc:
        logger.warning("Failed to extract text from %s: %s — skipping", pdf_path.name, exc)
        return None


def chunk_text(text: str) -> list[str]:
    """
    Chunk text using RecursiveCharacterTextSplitter.
    chunk_size=2048 characters (~512 tokens), chunk_overlap=256 (~12%).
    """
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    return splitter.split_text(text)


# ---------------------------------------------------------------------------
# Document processing
# ---------------------------------------------------------------------------


def process_fomc_documents() -> list[dict]:
    """
    Download FOMC PDFs from manifest URLs, extract text, and return document records.
    Each record: {doc_id, text, metadata} where metadata contains all payload fields.
    """
    logger.info("=== Processing FOMC documents ===")
    manifest = json.loads(FOMC_MANIFEST.read_text())
    logger.info("FOMC manifest: %d documents", len(manifest))

    documents = []
    download_failures = []

    for entry in manifest:
        doc_id = entry["doc_id"]
        url = entry["url"]
        dest_path = FOMC_DATA_DIR / f"{doc_id}.pdf"

        success = download_fomc_pdf(url, dest_path)
        if not success:
            download_failures.append({"doc_id": doc_id, "url": url})
            continue

        text = extract_text_from_pdf(dest_path)
        if text is None:
            logger.warning("No text extracted from %s — skipping", doc_id)
            continue

        documents.append(
            {
                "doc_id": doc_id,
                "text": text,
                "source": "fomc",
                "doc_type": entry["doc_type"],
                "document_date": entry["date"],
                "title": entry["title"],
                "regime_context": entry.get("regime_context", ""),
                "lang": "en",
            }
        )

    if download_failures:
        logger.warning(
            "FOMC download failures (%d): %s",
            len(download_failures),
            [f["doc_id"] for f in download_failures],
        )

    logger.info("FOMC: %d documents ready for chunking", len(documents))
    return documents


def process_sbv_documents() -> list[dict]:
    """
    Read SBV PDFs from data/sbv/ directory based on manifest entries with non-null filenames.
    Skips entries where filename is null (awaiting manual curation).
    """
    logger.info("=== Processing SBV documents ===")
    manifest = json.loads(SBV_MANIFEST.read_text())
    logger.info("SBV manifest: %d entries total", len(manifest))

    documents = []
    skipped_null = 0

    for entry in manifest:
        doc_id = entry["doc_id"]
        filename = entry.get("filename")

        if filename is None:
            skipped_null += 1
            continue

        pdf_path = SBV_DATA_DIR / filename
        if not pdf_path.exists():
            logger.warning("SBV file not found: %s — skipping %s", pdf_path, doc_id)
            continue

        lang = entry.get("lang", "en")
        if lang != "en":
            logger.warning(
                "SBV document %s is lang='%s' — bge-small-en-v1.5 is English-only; "
                "embedding quality will be degraded. Consider using the English portal version.",
                doc_id,
                lang,
            )

        text = extract_text_from_pdf(pdf_path)
        if text is None:
            logger.warning("No text extracted from %s — skipping", doc_id)
            continue

        documents.append(
            {
                "doc_id": doc_id,
                "text": text,
                "source": "sbv",
                "doc_type": entry["doc_type"],
                "document_date": entry["date"],
                "title": entry["title"],
                "regime_context": entry.get("regime_context", ""),
                "lang": lang,
            }
        )

    logger.info(
        "SBV: %d documents ready for chunking (%d skipped — null filename, awaiting manual curation)",
        len(documents),
        skipped_null,
    )
    return documents


# ---------------------------------------------------------------------------
# Embedding + upsert
# ---------------------------------------------------------------------------


def build_points(documents: list[dict]) -> list[PointStruct]:
    """
    Chunk all documents, embed with FastEmbed, and return Qdrant PointStruct list.
    Uses deterministic UUIDs for idempotent re-runs.
    """
    if not documents:
        logger.warning("No documents to embed — skipping embedding step")
        return []

    logger.info("=== Chunking %d documents ===", len(documents))

    all_chunks: list[dict] = []
    for doc in documents:
        chunks = chunk_text(doc["text"])
        total_chunks = len(chunks)
        logger.info("  %s: %d chunks", doc["doc_id"], total_chunks)

        for idx, chunk_text_content in enumerate(chunks):
            all_chunks.append(
                {
                    "point_id": make_point_id(doc["doc_id"], idx),
                    "text": chunk_text_content,
                    "payload": {
                        "text": chunk_text_content,
                        "source": doc["source"],
                        "doc_id": doc["doc_id"],
                        "doc_type": doc["doc_type"],
                        "document_date": doc["document_date"],
                        "title": doc["title"],
                        "chunk_index": idx,
                        "total_chunks": total_chunks,
                        "regime_context": doc["regime_context"],
                        "lang": doc["lang"],
                    },
                }
            )

    logger.info("Total chunks to embed: %d", len(all_chunks))

    logger.info("=== Embedding with FastEmbed %s ===", EMBED_MODEL)
    embedding_model = TextEmbedding(model_name=EMBED_MODEL)

    texts = [c["text"] for c in all_chunks]
    t0 = time.time()

    embeddings = list(embedding_model.embed(texts, batch_size=EMBED_BATCH_SIZE))

    elapsed = time.time() - t0
    logger.info(
        "Embedded %d chunks in %.1fs (%.0f chunks/sec)",
        len(embeddings),
        elapsed,
        len(embeddings) / elapsed if elapsed > 0 else 0,
    )

    points = [
        PointStruct(
            id=chunk["point_id"],
            vector=embeddings[i].tolist(),
            payload=chunk["payload"],
        )
        for i, chunk in enumerate(all_chunks)
    ]

    return points


def upsert_to_qdrant(client: QdrantClient, points: list[PointStruct]) -> int:
    """
    Upsert points to Qdrant macro_docs_v1 collection in batches.
    Returns total count of points upserted.
    """
    if not points:
        logger.warning("No points to upsert")
        return 0

    logger.info("=== Upserting %d points to Qdrant collection '%s' ===", len(points), COLLECTION_NAME)

    total_upserted = 0
    for batch_start in range(0, len(points), UPLOAD_BATCH_SIZE):
        batch = points[batch_start : batch_start + UPLOAD_BATCH_SIZE]
        client.upload_points(
            collection_name=COLLECTION_NAME,
            points=batch,
            wait=True,
        )
        total_upserted += len(batch)
        logger.info(
            "  Upserted batch %d-%d / %d",
            batch_start + 1,
            batch_start + len(batch),
            len(points),
        )

    return total_upserted


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def validate_population(client: QdrantClient, expected_min: int) -> None:
    """
    Validate collection after population:
    1. Check total point count
    2. Run similarity search for 'Federal Reserve rate decision'
    """
    logger.info("=== Validating Qdrant collection '%s' ===", COLLECTION_NAME)

    info = client.get_collection(COLLECTION_NAME)
    point_count = info.points_count
    logger.info("Collection point count: %d (expected >= %d)", point_count, expected_min)

    if point_count < expected_min:
        logger.warning(
            "Point count %d is below expected minimum %d", point_count, expected_min
        )

    # Test similarity search
    query_text = "Federal Reserve rate decision"
    logger.info("Running test search: '%s'", query_text)

    embedding_model = TextEmbedding(model_name=EMBED_MODEL)
    query_embedding = list(embedding_model.embed([query_text]))[0].tolist()

    results = client.search(
        collection_name=COLLECTION_NAME,
        query_vector=query_embedding,
        limit=3,
    )

    if not results:
        logger.warning("No results returned from test search — collection may be empty")
        return

    logger.info("Top-3 similarity search results for '%s':", query_text)
    for rank, result in enumerate(results, start=1):
        score = result.score
        doc_id = result.payload.get("doc_id", "unknown")
        doc_date = result.payload.get("document_date", "unknown")
        title = result.payload.get("title", "unknown")[:60]
        logger.info(
            "  #%d  score=%.4f  doc_id=%s  date=%s  title=%s...",
            rank,
            score,
            doc_id,
            doc_date,
            title,
        )

        if score < 0.7:
            logger.warning(
                "Search result #%d has score %.4f below 0.7 threshold", rank, score
            )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    logger.info("seed-qdrant-macro-docs.py — Phase 4 | Plan 03 | Requirement: DATA-03")
    logger.info("Qdrant target: %s:%d  collection: %s", QDRANT_HOST, QDRANT_PORT, COLLECTION_NAME)

    # Connect to Qdrant
    client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT, api_key=QDRANT_API_KEY)

    # Verify collection exists
    collections = [c.name for c in client.get_collections().collections]
    if COLLECTION_NAME not in collections:
        raise RuntimeError(
            f"Collection '{COLLECTION_NAME}' does not exist. "
            "Run init-qdrant.sh first to create the collection."
        )
    logger.info("Collection '%s' confirmed present", COLLECTION_NAME)

    # Process documents
    fomc_docs = process_fomc_documents()
    sbv_docs = process_sbv_documents()
    all_docs = fomc_docs + sbv_docs

    if not all_docs:
        logger.warning(
            "No documents available for embedding. "
            "FOMC downloads may have failed, or SBV filenames are all null. "
            "Run the script again after placing PDFs in data/sbv/ and updating filenames."
        )
        return

    # Build points (chunk + embed)
    points = build_points(all_docs)

    # Upsert to Qdrant
    total_upserted = upsert_to_qdrant(client, points)

    # Validate
    validate_population(client, expected_min=1)

    # Summary
    doc_count = len(all_docs)
    logger.info(
        "=== COMPLETE: Uploaded %d chunks from %d documents to %s ===",
        total_upserted,
        doc_count,
        COLLECTION_ALIAS,
    )
    logger.info(
        "  FOMC documents: %d | SBV documents: %d",
        len(fomc_docs),
        len(sbv_docs),
    )


if __name__ == "__main__":
    main()
