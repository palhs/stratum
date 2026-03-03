// =============================================================================
// 01_constraints.cypher — Node Uniqueness Constraints
// Phase 1 | Plan 02 | Requirement: INFRA-01, MACRO-01
//
// Runs against: neo4j user database (not system)
// Executed by: neo4j-init service with -d neo4j flag
//
// Neo4j Community Edition supports uniqueness constraints.
// IF NOT EXISTS ensures idempotency — safe to re-run.
// =============================================================================

// Regime node: each regime has a unique ID
// e.g., "stagflation_1970s", "expansion_2009_2019"
CREATE CONSTRAINT regime_id_unique IF NOT EXISTS
FOR (r:Regime) REQUIRE r.id IS UNIQUE;

// TimePeriod node: each time period segment has a unique ID
// e.g., "1970Q1", "2023H1"
CREATE CONSTRAINT time_period_id_unique IF NOT EXISTS
FOR (t:TimePeriod) REQUIRE t.id IS UNIQUE;
