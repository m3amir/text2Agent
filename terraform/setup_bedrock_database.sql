-- Setup script for Bedrock Knowledge Base database requirements
-- Run this script against your Aurora PostgreSQL database after deployment

-- Install the pgvector extension (version 0.5.0 or higher)
CREATE EXTENSION IF NOT EXISTS vector;

-- Create the bedrock_integration schema
CREATE SCHEMA IF NOT EXISTS bedrock_integration;

-- Create the bedrock_user role
CREATE ROLE bedrock_user WITH PASSWORD 'rY:n(srYQ3A9Ir3?' LOGIN;

-- Grant permissions to bedrock_user
GRANT ALL ON SCHEMA bedrock_integration TO bedrock_user;

-- Create the bedrock_kb table for Titan v2 embeddings (1024 dimensions)
CREATE TABLE IF NOT EXISTS bedrock_integration.bedrock_kb (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    embedding vector(1024),
    chunks text,
    metadata json,
    custom_metadata jsonb
);

-- Grant table permissions to bedrock_user
GRANT ALL ON TABLE bedrock_integration.bedrock_kb TO bedrock_user;

-- Create optimized indexes
-- HNSW index for vector similarity search with cosine distance
CREATE INDEX IF NOT EXISTS bedrock_kb_embedding_idx 
ON bedrock_integration.bedrock_kb 
USING hnsw (embedding vector_cosine_ops);

-- GIN index for full-text search on chunks
CREATE INDEX IF NOT EXISTS bedrock_kb_chunks_idx 
ON bedrock_integration.bedrock_kb 
USING gin (to_tsvector('simple', chunks));

-- GIN index for metadata search
CREATE INDEX IF NOT EXISTS bedrock_kb_metadata_idx 
ON bedrock_integration.bedrock_kb 
USING gin (custom_metadata);

-- Display success message
SELECT 'Bedrock Knowledge Base database setup completed successfully!' as status;
