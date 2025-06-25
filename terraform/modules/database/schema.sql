-- Database initialization script for text2Agent
-- This script creates the required schema and tables for tenant management

-- Create the Tenants schema
CREATE SCHEMA IF NOT EXISTS "Tenants";

-- Create the tenantmappings table in the Tenants schema
CREATE TABLE IF NOT EXISTS "Tenants"."tenantmappings" (
    id SERIAL PRIMARY KEY,
    tenant_id UUID NOT NULL UNIQUE,
    domain VARCHAR(255) NOT NULL,
    bucket_name VARCHAR(255) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT unique_domain UNIQUE (domain),
    CONSTRAINT unique_bucket UNIQUE (bucket_name)
);

-- Create index on domain for faster lookups
CREATE INDEX IF NOT EXISTS idx_tenantmappings_domain ON "Tenants"."tenantmappings" (domain);

-- Create the users table (if needed for user management)
CREATE TABLE IF NOT EXISTS "Tenants"."users" (
    id SERIAL PRIMARY KEY,
    user_id UUID NOT NULL UNIQUE,
    email VARCHAR(255) NOT NULL UNIQUE,
    name VARCHAR(255) NOT NULL,
    tenant_id UUID NOT NULL,
    cognito_sub VARCHAR(255) UNIQUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_tenant FOREIGN KEY (tenant_id) REFERENCES "Tenants"."tenantmappings" (tenant_id) ON DELETE CASCADE
);

-- Create indexes for users table
CREATE INDEX IF NOT EXISTS idx_users_email ON "Tenants"."users" (email);
CREATE INDEX IF NOT EXISTS idx_users_tenant_id ON "Tenants"."users" (tenant_id);
CREATE INDEX IF NOT EXISTS idx_users_cognito_sub ON "Tenants"."users" (cognito_sub);

-- Create a trigger to update the updated_at column
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Apply the trigger to both tables
CREATE TRIGGER update_tenantmappings_updated_at 
    BEFORE UPDATE ON "Tenants"."tenantmappings" 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_users_updated_at 
    BEFORE UPDATE ON "Tenants"."users" 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Grant permissions (adjust as needed)
-- These permissions allow the application user to read/write data
GRANT USAGE ON SCHEMA "Tenants" TO postgres;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA "Tenants" TO postgres;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA "Tenants" TO postgres; 