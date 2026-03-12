#!/usr/bin/env python3
"""
seed-qdrant-macro-docs.py — Populate Qdrant macro_docs with FOMC + SBV documents.
Phase 4 | Plan 03 | Requirement: DATA-03

Usage:
    python scripts/seed-qdrant-macro-docs.py

Downloads FOMC PDFs from federalreserve.gov. For SBV documents, reads PDFs from
data/sbv/ when available, or generates structured policy summaries via Gemini API
from manifest metadata (with JSON caching for idempotent re-runs).

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
from fastembed import TextEmbedding, SparseTextEmbedding
from langchain_text_splitters import RecursiveCharacterTextSplitter
from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct, SparseVector

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
# Internal Docker network uses plain HTTP; disable TLS for local Qdrant.
QDRANT_HTTPS = os.getenv("QDRANT_HTTPS", "false").lower() in ("true", "1", "yes")

if not QDRANT_API_KEY:
    raise EnvironmentError("QDRANT_API_KEY environment variable is required")

COLLECTION_NAME = "macro_docs_v1"
COLLECTION_ALIAS = "macro_docs"
EMBED_MODEL = "BAAI/bge-small-en-v1.5"
SPARSE_MODEL = "Qdrant/bm25"
EMBED_BATCH_SIZE = 16
UPLOAD_BATCH_SIZE = 16

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
    Process SBV documents from manifest.
    - If a PDF exists (filename is set and file present), extract text from PDF.
    - Otherwise, generate a structured policy summary via Gemini API.
    Gemini-generated summaries are cached to data/sbv/generated_summaries.json
    for idempotent re-runs.
    """
    logger.info("=== Processing SBV documents ===")
    manifest = json.loads(SBV_MANIFEST.read_text())
    logger.info("SBV manifest: %d entries total", len(manifest))

    documents = []
    pdf_count = 0
    gemini_count = 0
    gemini_cache_hits = 0

    # Load Gemini summary cache
    cache_path = SBV_DATA_DIR / "generated_summaries.json"
    summary_cache: dict[str, str] = {}
    if cache_path.exists():
        summary_cache = json.loads(cache_path.read_text())
        logger.info("Loaded %d cached Gemini summaries", len(summary_cache))

    # Check if Gemini is available for entries without PDFs
    gemini_model = None
    needs_gemini = any(
        entry.get("filename") is None or not (SBV_DATA_DIR / entry["filename"]).exists()
        for entry in manifest
        if entry.get("filename") is not None
    ) or any(entry.get("filename") is None for entry in manifest)

    if needs_gemini:
        gemini_api_key = os.getenv("GEMINI_API_KEY")
        if gemini_api_key:
            try:
                from google import genai
                gemini_model = genai.Client(api_key=gemini_api_key)
                logger.info("Gemini API available — will generate SBV policy summaries")
            except Exception as exc:
                logger.warning("Failed to initialize Gemini: %s — entries without PDFs will be skipped", exc)
        else:
            logger.warning("GEMINI_API_KEY not set — entries without PDFs will be skipped")

    for entry in manifest:
        doc_id = entry["doc_id"]
        filename = entry.get("filename")
        text = None

        # Try PDF first
        if filename is not None:
            pdf_path = SBV_DATA_DIR / filename
            if pdf_path.exists():
                lang = entry.get("lang", "en")
                if lang != "en":
                    logger.warning(
                        "SBV document %s is lang='%s' — bge-small-en-v1.5 is English-only; "
                        "embedding quality will be degraded.",
                        doc_id, lang,
                    )
                text = extract_text_from_pdf(pdf_path)
                if text:
                    pdf_count += 1

        # Fall back to Gemini-generated summary
        if text is None:
            if doc_id in summary_cache:
                text = summary_cache[doc_id]
                gemini_cache_hits += 1
            elif gemini_model is not None:
                text = _generate_sbv_summary(gemini_model, entry)
                if text:
                    summary_cache[doc_id] = text
                    gemini_count += 1

        if text is None:
            logger.info("  [%s] No PDF and no Gemini — skipping", doc_id)
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
                "lang": "en",
            }
        )

    # Save updated cache
    if gemini_count > 0:
        cache_path.write_text(json.dumps(summary_cache, indent=2, ensure_ascii=False))
        logger.info("Saved %d Gemini summaries to cache", len(summary_cache))

    logger.info(
        "SBV: %d documents ready (%d from PDF, %d from Gemini, %d cache hits)",
        len(documents), pdf_count, gemini_count, gemini_cache_hits,
    )
    return documents


_SBV_PROMPT_TEMPLATE = """You are a macroeconomic analyst specializing in Vietnamese monetary policy.
Write a detailed English-language policy summary for the following State Bank of Vietnam (SBV) document.

Document: {title}
Date: {date}
Type: {doc_type}
Regime context: {regime_context}

Write 400-600 words covering:
1. The specific policy action taken by SBV (rate changes, circulars, credit directives)
2. The macroeconomic context driving the decision (inflation, GDP growth, VND/USD, credit conditions)
3. How this relates to the global monetary environment at the time (Fed policy, capital flows)
4. The expected and actual impact on Vietnamese financial markets
5. Key metrics: refinancing rate, deposit rate ceiling, credit growth target, VND/USD rate if relevant

Write in a factual, analytical tone suitable for financial research. Use specific numbers and dates where known.
Do NOT include disclaimers about being AI-generated."""


def _generate_sbv_summary(client, entry: dict) -> Optional[str]:
    """Generate an SBV policy summary via Gemini with retry."""
    doc_id = entry["doc_id"]
    prompt = _SBV_PROMPT_TEMPLATE.format(
        title=entry["title"],
        date=entry["date"],
        doc_type=entry["doc_type"],
        regime_context=entry.get("regime_context", "unknown"),
    )

    for attempt in range(3):
        try:
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt,
            )
            text = (response.text or "").strip()
            if text and len(text) > 100:
                logger.info("  [%s] Gemini summary: %d chars", doc_id, len(text))
                return text
            logger.warning("  [%s] Gemini returned short/empty response", doc_id)
            return None
        except Exception as exc:
            wait = 2 ** (attempt + 1)
            logger.warning("  [%s] Gemini attempt %d failed: %s — retrying in %ds", doc_id, attempt + 1, exc, wait)
            time.sleep(wait)

    logger.warning("  [%s] Gemini failed after 3 attempts — skipping", doc_id)
    return None


# ---------------------------------------------------------------------------
# Embedding + upsert
# ---------------------------------------------------------------------------


def chunk_documents(documents: list[dict]) -> list[dict]:
    """Chunk all documents into metadata dicts (without embeddings). Low memory."""
    if not documents:
        logger.warning("No documents to chunk — skipping")
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
    return all_chunks


def embed_and_upsert(client: QdrantClient, all_chunks: list[dict]) -> int:
    """
    Embed and upsert chunks in streaming batches to minimize peak memory.
    Processes EMBED_BATCH_SIZE chunks at a time: embed → upsert → discard.
    """
    import gc

    if not all_chunks:
        logger.warning("No chunks to embed")
        return 0

    logger.info("=== Embedding with FastEmbed %s (dense) + %s (sparse BM25) ===", EMBED_MODEL, SPARSE_MODEL)
    embedding_model = TextEmbedding(model_name=EMBED_MODEL)
    sparse_model = SparseTextEmbedding(model_name=SPARSE_MODEL)

    total_upserted = 0
    total_chunks = len(all_chunks)
    t0 = time.time()

    for batch_start in range(0, total_chunks, EMBED_BATCH_SIZE):
        batch_chunks = all_chunks[batch_start : batch_start + EMBED_BATCH_SIZE]
        batch_texts = [c["text"] for c in batch_chunks]

        # Embed this batch — dense (384-dim) + sparse BM25
        dense_embeddings = list(embedding_model.embed(batch_texts, batch_size=EMBED_BATCH_SIZE))
        sparse_embeddings = list(sparse_model.embed(batch_texts, batch_size=EMBED_BATCH_SIZE))

        # Build points with named vectors for LlamaIndex hybrid search
        points = [
            PointStruct(
                id=chunk["point_id"],
                vector={
                    "text-dense": dense_embeddings[j].tolist(),
                    "text-sparse": SparseVector(
                        indices=sparse_embeddings[j].indices.tolist(),
                        values=sparse_embeddings[j].values.tolist(),
                    ),
                },
                payload=chunk["payload"],
            )
            for j, chunk in enumerate(batch_chunks)
        ]

        # Upsert immediately
        client.upload_points(
            collection_name=COLLECTION_NAME,
            points=points,
            wait=True,
        )
        total_upserted += len(points)
        logger.info(
            "  Embedded+upserted batch %d-%d / %d",
            batch_start + 1,
            batch_start + len(points),
            total_chunks,
        )

        # Free batch memory
        del dense_embeddings, sparse_embeddings, points, batch_texts, batch_chunks
        gc.collect()

    elapsed = time.time() - t0
    logger.info(
        "Embedded and upserted %d chunks in %.1fs (%.0f chunks/sec)",
        total_upserted,
        elapsed,
        total_upserted / elapsed if elapsed > 0 else 0,
    )

    return total_upserted


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def validate_population(client: QdrantClient, expected_min: int) -> None:
    """
    Validate collection after population:
    1. Check total point count
    2. Check per-source counts (FOMC vs SBV)
    """
    from qdrant_client.models import Filter, FieldCondition, MatchValue

    logger.info("=== Validating Qdrant collection '%s' ===", COLLECTION_NAME)

    info = client.get_collection(COLLECTION_NAME)
    point_count = info.points_count
    logger.info("Collection point count: %d (expected >= %d)", point_count, expected_min)

    if point_count < expected_min:
        logger.warning(
            "Point count %d is below expected minimum %d", point_count, expected_min
        )

    # Check per-source counts
    for source in ("FOMC", "SBV"):
        count = client.count(
            collection_name=COLLECTION_NAME,
            count_filter=Filter(
                must=[FieldCondition(key="source", match=MatchValue(value=source))]
            ),
            exact=True,
        )
        logger.info("  %s points: %d", source, count.count)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    logger.info("seed-qdrant-macro-docs.py — Phase 4 | Plan 03 | Requirement: DATA-03")
    logger.info("Qdrant target: %s:%d  collection: %s", QDRANT_HOST, QDRANT_PORT, COLLECTION_NAME)

    # Connect to Qdrant
    client = QdrantClient(
        host=QDRANT_HOST, port=QDRANT_PORT, api_key=QDRANT_API_KEY, https=QDRANT_HTTPS,
    )

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

    # Capture counts before freeing memory
    fomc_count = len(fomc_docs)
    sbv_count = len(sbv_docs)
    doc_count = len(all_docs)

    # Free document text memory before embedding
    all_chunks = chunk_documents(all_docs)
    del all_docs, fomc_docs, sbv_docs

    # Embed and upsert in streaming batches (memory-safe)
    total_upserted = embed_and_upsert(client, all_chunks)
    del all_chunks

    # Validate
    validate_population(client, expected_min=1)

    # Summary
    logger.info(
        "=== COMPLETE: Uploaded %d chunks from %d documents to %s ===",
        total_upserted,
        doc_count,
        COLLECTION_ALIAS,
    )
    logger.info(
        "  FOMC documents: %d | SBV documents: %d",
        fomc_count,
        sbv_count,
    )


if __name__ == "__main__":
    main()
