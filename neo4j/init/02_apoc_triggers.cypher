// =============================================================================
// 02_apoc_triggers.cypher — APOC Trigger: RESEMBLES Property Enforcement
// Phase 1 | Plan 02 | Requirement: INFRA-01, MACRO-04
//
// Runs against: system database (Neo4j 5.x requirement for apoc.trigger.install)
// Executed by: neo4j-init service with -d system flag
//
// Context: Neo4j Community Edition does NOT support relationship property
// existence constraints. APOC Core triggers are the verified workaround.
//
// This trigger enforces that all RESEMBLES relationships carry:
//   - similarity_score (FLOAT)  — cosine similarity of the two regimes
//   - dimensions_matched (LIST<STRING>) — which macro dimensions aligned
//   - period (STRING) — the time period label for this comparison
//
// Without these properties, RESEMBLES relationships are semantically invalid
// and would break Phase 4 analogue retrieval logic (MACRO-04).
//
// References:
//   - RESEARCH.md Pitfall 1: Neo4j 5.x uses apoc.trigger.install (not add)
//   - apoc.trigger.install first argument is the target database ('neo4j')
//   - apoc.trigger.start must be called after install to activate the trigger
// =============================================================================

// ---------------------------------------------------------------------------
// Drop existing trigger first for idempotency
// Silently fails on first run when trigger does not yet exist
// ---------------------------------------------------------------------------
CALL apoc.trigger.drop('neo4j', 'enforce_resembles_properties')
YIELD name
RETURN name;

// ---------------------------------------------------------------------------
// Install RESEMBLES property enforcement trigger
// ---------------------------------------------------------------------------
CALL apoc.trigger.install(
  'neo4j',
  'enforce_resembles_properties',
  'UNWIND [rel IN $createdRelationships WHERE type(rel) = "RESEMBLES"] AS r
   WITH r
   WHERE r.similarity_score IS NULL OR r.dimensions_matched IS NULL OR r.period IS NULL
   CALL apoc.util.validate(
     true,
     "RESEMBLES relationship missing required properties: similarity_score, dimensions_matched, period. Got: similarity_score=%s, dimensions_matched=%s, period=%s",
     [r.similarity_score, r.dimensions_matched, r.period]
   )
   RETURN null',
  {phase: 'before'}
)
YIELD name
RETURN name;

// ---------------------------------------------------------------------------
// Activate the trigger
// ---------------------------------------------------------------------------
CALL apoc.trigger.start('neo4j', 'enforce_resembles_properties')
YIELD name
RETURN name;
