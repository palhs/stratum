#!/bin/sh
# =============================================================================
# scripts/init-qdrant.sh — One-shot Qdrant collection initialization
#
# Runs as a Docker Compose one-shot service after qdrant health check passes.
# Creates versioned collections with stable aliases for hot-swap versioning.
#
# Environment variables (set in docker-compose.yml):
#   QDRANT_API_KEY  — Qdrant service API key
#   QDRANT_HOST     — Qdrant hostname (default: qdrant)
#   QDRANT_PORT     — Qdrant port (default: 6333)
#
# Vector size: 384 — matches FastEmbed default model (BAAI/bge-small-en-v1.5)
# Distance: Cosine (standard for semantic similarity)
#
# Alias versioning pattern: stable aliases (macro_embeddings) point to versioned
# collections (macro_embeddings_v1). When the embedding model changes, create v2,
# update the alias — no client code changes, zero downtime.
#
# Collections:
#   - macro_embeddings_v1, valuation_embeddings_v1, structure_embeddings_v1:
#     Single unnamed vector (legacy embedding collections, not used for hybrid search)
#   - macro_docs_v1, earnings_docs_v1:
#     Named vectors (text-dense + text-sparse) for LlamaIndex hybrid search (Phase 5+)
#
# This script is idempotent for embedding collections but RECREATES hybrid
# collections (macro_docs_v1, earnings_docs_v1) to ensure correct named-vector config.
# =============================================================================

set -e

QDRANT_HOST="${QDRANT_HOST:-qdrant}"
QDRANT_PORT="${QDRANT_PORT:-6333}"
BASE_URL="http://${QDRANT_HOST}:${QDRANT_PORT}"

echo "================================================="
echo "Qdrant Collection Initialization"
echo "Target: ${BASE_URL}"
echo "================================================="

# ---------------------------------------------------------------------------
# Wait for Qdrant to be ready (belt-and-suspenders — health check should handle this)
# ---------------------------------------------------------------------------
echo "Waiting for Qdrant..."
until curl -sf "${BASE_URL}/healthz" > /dev/null 2>&1; do
  sleep 2
done
echo "Qdrant is ready."

# ---------------------------------------------------------------------------
# Helper: create collection if it does not already exist
# Used for the three legacy embedding collections (single unnamed vector).
# ---------------------------------------------------------------------------
create_collection_if_missing() {
    local collection="$1"
    local vector_size="$2"
    local distance="${3:-Cosine}"

    echo ""
    echo "Creating collection: ${collection} (size=${vector_size}, distance=${distance})"

    # Check if collection already exists
    status=$(curl -s -o /dev/null -w "%{http_code}" \
        -H "api-key: ${QDRANT_API_KEY}" \
        "${BASE_URL}/collections/${collection}")

    if [ "${status}" = "200" ]; then
        echo "  Collection '${collection}' already exists — skipping."
        return 0
    fi

    # Create versioned collection
    curl -s -f -X PUT "${BASE_URL}/collections/${collection}" \
        -H "Content-Type: application/json" \
        -H "api-key: ${QDRANT_API_KEY}" \
        --data-raw "{
            \"vectors\": {
                \"size\": ${vector_size},
                \"distance\": \"${distance}\"
            }
        }" > /dev/null

    echo "  Created '${collection}'."
}

# ---------------------------------------------------------------------------
# Helper: create or update an alias pointing to a collection
# ---------------------------------------------------------------------------
create_alias() {
    local alias_name="$1"
    local collection_name="$2"

    echo "  Creating alias '${alias_name}' -> '${collection_name}'"

    curl -s -f -X POST "${BASE_URL}/collections/aliases" \
        -H "Content-Type: application/json" \
        -H "api-key: ${QDRANT_API_KEY}" \
        --data-raw "{
            \"actions\": [
                {
                    \"create_alias\": {
                        \"collection_name\": \"${collection_name}\",
                        \"alias_name\": \"${alias_name}\"
                    }
                }
            ]
        }" > /dev/null

    echo "  Alias '${alias_name}' created."
}

# ---------------------------------------------------------------------------
# Helper: recreate a hybrid collection with named-vector config.
# Used for macro_docs_v1 and earnings_docs_v1 (LlamaIndex hybrid search).
#
# Named vectors required by LlamaIndex QdrantVectorStore with enable_hybrid=True:
#   text-dense:  384-dim Cosine — dense embeddings from BAAI/bge-small-en-v1.5
#   text-sparse: sparse Dot with IDF modifier — BM25 sparse vectors
#
# IMPORTANT: This function DELETES and RECREATES the collection to ensure
# correct named-vector config. Re-run seed scripts after calling this.
# ---------------------------------------------------------------------------
recreate_hybrid_collection() {
    local collection="$1"

    echo ""
    echo "Recreating ${collection} with named vector config for hybrid search"

    # Delete if exists
    status=$(curl -s -o /dev/null -w "%{http_code}" \
        -H "api-key: ${QDRANT_API_KEY}" \
        "${BASE_URL}/collections/${collection}")

    if [ "${status}" = "200" ]; then
        echo "  Deleting existing collection '${collection}'..."
        curl -s -f -X DELETE "${BASE_URL}/collections/${collection}" \
            -H "api-key: ${QDRANT_API_KEY}" > /dev/null
        echo "  Deleted '${collection}'."
    fi

    # Create with named-vector config for hybrid search
    curl -s -f -X PUT "${BASE_URL}/collections/${collection}" \
        -H "Content-Type: application/json" \
        -H "api-key: ${QDRANT_API_KEY}" \
        --data-raw "{
            \"vectors\": {
                \"text-dense\": {
                    \"size\": 384,
                    \"distance\": \"Cosine\"
                }
            },
            \"sparse_vectors\": {
                \"text-sparse\": {
                    \"modifier\": \"idf\"
                }
            }
        }" > /dev/null

    echo "  Created '${collection}' with text-dense (384, Cosine) + text-sparse (IDF)."
}

# ---------------------------------------------------------------------------
# Collections
#
# Vector size 384 matches FastEmbed default model (BAAI/bge-small-en-v1.5).
# More memory-efficient than 1536 (OpenAI) for the 8GB VPS.
# If the embedding model changes, create a new versioned collection (v2, v3, ...)
# and update the alias — zero downtime, no client code changes.
# ---------------------------------------------------------------------------

# Macro regime embeddings (for regime analogue similarity search — MACRO-04)
create_collection_if_missing "macro_embeddings_v1" 384 "Cosine"
create_alias "macro_embeddings" "macro_embeddings_v1"

# Valuation context embeddings (for historical valuation narrative retrieval)
create_collection_if_missing "valuation_embeddings_v1" 384 "Cosine"
create_alias "valuation_embeddings" "valuation_embeddings_v1"

# Price structure embeddings (for pattern-based structure context)
create_collection_if_missing "structure_embeddings_v1" 384 "Cosine"
create_alias "structure_embeddings" "structure_embeddings_v1"

# ---------------------------------------------------------------------------
# Document corpus collections (Phase 4 — DATA-03, DATA-04)
# Hybrid search collections with named vectors for LlamaIndex QdrantVectorStore.
# These are RECREATED on each init run to ensure correct named-vector config.
# After running this script, re-run the seed scripts to repopulate.
# ---------------------------------------------------------------------------

# Macro document corpus (Fed FOMC minutes + SBV monetary policy reports)
recreate_hybrid_collection "macro_docs_v1"
create_alias "macro_docs" "macro_docs_v1"

# Earnings document corpus (VN30 company quarterly/annual reports)
recreate_hybrid_collection "earnings_docs_v1"
create_alias "earnings_docs" "earnings_docs_v1"

echo ""
echo "================================================="
echo "Qdrant initialization complete."
echo "Collections created:"
curl -s -H "api-key: ${QDRANT_API_KEY}" "${BASE_URL}/collections" | \
    grep -o '"name":"[^"]*"' | sed 's/"name":"//;s/"//' | sed 's/^/  - /'
echo ""
echo "NOTE: macro_docs_v1 and earnings_docs_v1 were recreated with named-vector"
echo "      config for LlamaIndex hybrid search. Re-run seed scripts to repopulate:"
echo "        python scripts/seed-qdrant-macro-docs.py"
echo "        python scripts/seed-qdrant-earnings-docs.py"
echo "================================================="
