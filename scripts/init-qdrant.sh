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
# Helper: create collection if it does not already exist
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
# Collections
#
# Vector size 1536 matches OpenAI text-embedding-3-small and text-embedding-ada-002.
# If the embedding model changes, create a new versioned collection (v2, v3, ...)
# and update the alias — zero downtime, no client code changes.
# ---------------------------------------------------------------------------

# Macro regime embeddings (for regime analogue similarity search)
create_collection_if_missing "macro_embeddings_v1" 1536 "Cosine"
create_alias "macro_embeddings" "macro_embeddings_v1"

# Valuation context embeddings (for historical valuation narrative retrieval)
create_collection_if_missing "valuation_embeddings_v1" 1536 "Cosine"
create_alias "valuation_embeddings" "valuation_embeddings_v1"

# Price structure embeddings (for pattern-based structure context)
create_collection_if_missing "structure_embeddings_v1" 1536 "Cosine"
create_alias "structure_embeddings" "structure_embeddings_v1"

echo ""
echo "================================================="
echo "Qdrant initialization complete."
echo "Collections created:"
curl -s -H "api-key: ${QDRANT_API_KEY}" "${BASE_URL}/collections" | \
    grep -o '"name":"[^"]*"' | sed 's/"name":"//;s/"//' | sed 's/^/  - /'
echo "================================================="
