-- =============================================================================
-- create-n8n-db.sql — Bootstrap n8n metadata database
--
-- Location: /docker-entrypoint-initdb.d/create-n8n-db.sql
-- Runs ONCE on first PostgreSQL container start (via initdb mechanism).
-- Subsequent starts skip this file — initdb only runs on empty data volume.
--
-- Purpose: n8n requires its own database separate from the stratum application
-- database. This isolates n8n metadata (workflow definitions, credentials,
-- execution history) from application time-series data.
-- =============================================================================

-- Create n8n_meta database only if it does not already exist
SELECT 'CREATE DATABASE n8n_meta'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'n8n_meta')\gexec
