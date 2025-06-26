-- ==============================================================================
-- BEDROCK KNOWLEDGE BASE SCHEMA SETUP
-- Configures Aurora PostgreSQL for use with Amazon Bedrock Knowledge Base
-- Based on AWS official documentation requirements
-- ==============================================================================

-- Enable pgvector extension for vector operations
CREATE EXTENSION IF NOT EXISTS vector;

-- Create bedrock_integration schema for Knowledge Base
CREATE SCHEMA IF NOT EXISTS bedrock_integration;

-- Create the bedrock_kb table for AWS Bedrock Knowledge Base
-- This table stores document chunks as vectors with metadata
-- Table structure follows AWS Bedrock Knowledge Base requirements
CREATE TABLE IF NOT EXISTS bedrock_integration.bedrock_kb (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    chunks TEXT NOT NULL,
    embedding vector(1024),  -- Amazon Titan Text Embeddings v2 uses 1024 dimensions
    metadata JSONB
);

-- ==============================================================================
-- INDEXES FOR PERFORMANCE
-- ==============================================================================

-- HNSW index for vector similarity search (recommended for Aurora)
-- Uses cosine distance for semantic similarity
CREATE INDEX IF NOT EXISTS idx_bedrock_kb_embedding_hnsw 
ON bedrock_integration.bedrock_kb 
USING hnsw (embedding vector_cosine_ops);

-- GIN index for full-text search on chunks (required by Bedrock)
CREATE INDEX IF NOT EXISTS idx_bedrock_kb_chunks_gin 
ON bedrock_integration.bedrock_kb 
USING gin (to_tsvector('simple', chunks));

-- GIN index for metadata filtering
CREATE INDEX IF NOT EXISTS idx_bedrock_kb_metadata_gin 
ON bedrock_integration.bedrock_kb 
USING gin (metadata);

-- ==============================================================================
-- VERIFICATION
-- ==============================================================================

-- Check pgvector version
SELECT extversion FROM pg_extension WHERE extname='vector';

-- Verify table structure
\d bedrock_integration.bedrock_kb;

-- Grant necessary permissions (if needed for future role-based access)
-- Note: The RDS Data API uses the master user credentials, so no additional grants needed for now 