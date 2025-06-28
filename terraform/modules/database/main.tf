# VPC and subnet configuration passed from networking module
# These will be provided via variables

# Random password for database
resource "random_password" "db_password" {
  length           = 16
  special          = true
  override_special = "!#$%&*()-_=+[]{}<>:?"
}

# DB Subnet Group - use public subnets for dev (external access), private for prod
resource "aws_db_subnet_group" "main" {
  name       = "${var.project_name}-${var.environment}-db-subnet-group"
  subnet_ids = var.environment == "dev" && length(var.public_subnet_ids) > 0 ? var.public_subnet_ids : var.private_subnet_ids

  tags = {
    Name = "${var.project_name}-${var.environment}-db-subnet-group"
  }
}

# RDS Security Group
resource "aws_security_group" "rds" {
  name_prefix = "${var.project_name}-${var.environment}-rds-"
  vpc_id      = var.vpc_id

  ingress {
    from_port   = 5432
    to_port     = 5432
    protocol    = "tcp"
    cidr_blocks = [var.vpc_cidr_block]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "${var.project_name}-${var.environment}-rds-sg"
  }
}

# IAM Role for RDS Enhanced Monitoring
resource "aws_iam_role" "rds_enhanced_monitoring" {
  name = "${var.project_name}-${var.environment}-rds-monitoring-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "monitoring.rds.amazonaws.com"
        }
      }
    ]
  })

  tags = {
    Name = "${var.project_name}-${var.environment}-rds-monitoring-role"
  }
}

resource "aws_iam_role_policy_attachment" "rds_enhanced_monitoring" {
  role       = aws_iam_role.rds_enhanced_monitoring.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonRDSEnhancedMonitoringRole"
}

# Main Application RDS Aurora Cluster
resource "aws_rds_cluster" "main" {
  cluster_identifier = var.cluster_identifier != null ? var.cluster_identifier : "text2agent-${var.environment}-cluster"
  engine             = "aurora-postgresql"
  engine_version     = "16.6"
  engine_mode        = "provisioned"
  database_name      = "str_kb"
  master_username    = "postgres"
  master_password    = random_password.db_password.result

  db_subnet_group_name   = aws_db_subnet_group.main.name
  vpc_security_group_ids = [aws_security_group.rds.id]

  # Note: publicly_accessible is not supported for Aurora clusters - use manage_master_user_password instead

  backup_retention_period      = var.environment == "prod" ? 30 : 7
  preferred_backup_window      = "03:00-04:00"
  preferred_maintenance_window = "sun:04:00-sun:05:00"

  storage_encrypted         = true
  deletion_protection       = var.environment == "prod" ? true : false
  skip_final_snapshot       = var.environment == "dev" ? true : false
  final_snapshot_identifier = var.environment == "dev" ? null : "${var.project_name}-main-final-snapshot-${formatdate("YYYYMMDD-hhmm", timestamp())}"
  delete_automated_backups  = var.environment == "dev" ? true : false

  # Enable Data API
  enable_http_endpoint = true

  serverlessv2_scaling_configuration {
    max_capacity             = 2
    min_capacity             = 0
    seconds_until_auto_pause = 900 # 15 minutes auto-pause timeout
  }

  tags = {
    Name = "${var.project_name}-${var.environment}-main-aurora-cluster"
  }
}

# Main Application RDS Cluster Instance
resource "aws_rds_cluster_instance" "main" {
  count              = 1
  identifier         = "${aws_rds_cluster.main.cluster_identifier}-${count.index + 1}"
  cluster_identifier = aws_rds_cluster.main.id
  instance_class     = "db.serverless"
  engine             = aws_rds_cluster.main.engine
  engine_version     = aws_rds_cluster.main.engine_version

  performance_insights_enabled = true
  monitoring_interval          = 60
  monitoring_role_arn          = aws_iam_role.rds_enhanced_monitoring.arn

  auto_minor_version_upgrade = true

  tags = {
    Name = "${var.project_name}-${var.environment}-main-aurora-instance-${count.index + 1}"
  }
}

# Store database credentials in AWS Secrets Manager
resource "aws_secretsmanager_secret" "db_credentials" {
  name                           = "${var.project_name}-${var.environment}-db-credentials-v2"
  description                    = "Database credentials for ${var.project_name} ${var.environment}"
  force_overwrite_replica_secret = true
  recovery_window_in_days        = 0

  tags = {
    Name = "${var.project_name}-${var.environment}-db-credentials-v2"
  }
}

resource "aws_secretsmanager_secret_version" "db_credentials" {
  secret_id = aws_secretsmanager_secret.db_credentials.id
  secret_string = jsonencode({
    username = aws_rds_cluster.main.master_username
    password = aws_rds_cluster.main.master_password
    endpoint = aws_rds_cluster.main.endpoint
    port     = aws_rds_cluster.main.port
    dbname   = aws_rds_cluster.main.database_name
  })
}

# Database Schema Initialization using RDS Data API (GitHub Actions compatible)
resource "null_resource" "db_schema_init" {
  # This resource will re-run if the cluster endpoint changes
  triggers = {
    cluster_arn = aws_rds_cluster.main.arn
    secret_arn  = aws_secretsmanager_secret.db_credentials.arn
    # Force recreation to fix HNSW index creation
    force_recreate = "2025-01-01-hnsw-fix"
  }

  # Wait for the database to be ready - intelligent polling instead of fixed wait
  provisioner "local-exec" {
    command = <<-EOF
      echo "🔍 Checking database readiness..."
      
      # Smart wait - check every 30 seconds, max 5 minutes
      MAX_ATTEMPTS=10  # 10 attempts * 30 seconds = 5 minutes max
      ATTEMPT=0
      
      while [ $ATTEMPT -lt $MAX_ATTEMPTS ]; do
        ATTEMPT=$((ATTEMPT + 1))
        echo "⏱️  Attempt $ATTEMPT/$MAX_ATTEMPTS - Testing database connectivity..."
        
        # Test if we can connect and run a simple query
        if aws rds-data execute-statement \
          --resource-arn "${aws_rds_cluster.main.arn}" \
          --secret-arn "${aws_secretsmanager_secret.db_credentials.arn}" \
          --database "${aws_rds_cluster.main.database_name}" \
          --sql 'SELECT 1;' \
          --region ${var.aws_region} \
          --output text >/dev/null 2>&1; then
          
          echo "✅ Database is ready! (took $((ATTEMPT * 30)) seconds)"
          break
        else
          if [ $ATTEMPT -eq $MAX_ATTEMPTS ]; then
            echo "❌ Database not ready after $((MAX_ATTEMPTS * 30)) seconds"
            exit 1
          else
            echo "⏳ Database not ready yet, waiting 30 seconds..."
            sleep 30
          fi
        fi
      done
    EOF
  }

  # Initialize TWO separate databases using AWS CLI and RDS Data API
  provisioner "local-exec" {
    command = <<-EOF
      # Function to retry AWS RDS commands with resume handling
      retry_rds_command() {
        local max_attempts=8  # Increased for auto-pause scenarios
        local attempt=1
        local wait_time=30
        local description="$1"
        local command="$2"
        
        while [ $attempt -le $max_attempts ]; do
          echo "🔄 Attempt $attempt/$max_attempts: $description"
          
          # Capture both stdout and stderr for better error detection
          local output
          local exit_code
          output=$(eval "$command" 2>&1)
          exit_code=$?
          
          if [ $exit_code -eq 0 ]; then
            echo "✅ Success: $description"
            return 0
          else
            # Check for database resuming exceptions in the output
            if echo "$output" | grep -qi "DatabaseResumingException\|resuming\|auto-pause"; then
              echo "⏳ Database resuming from auto-pause, waiting ${wait_time}s..."
              echo "   Error details: $(echo "$output" | head -n 2)"
              sleep $wait_time
              # Increase wait time for subsequent attempts (auto-pause can take time)
              wait_time=$((wait_time + 20))
            elif echo "$output" | grep -qi "already exists\|duplicate\|unique constraint"; then
              echo "ℹ️  Resource already exists: $description"
              return 0  # Treat as success for idempotent operations
            else
              echo "⚠️  Command failed (non-resume error): $description"
              echo "   Error details: $(echo "$output" | head -n 3)"
              return 1
            fi
          fi
          
          attempt=$((attempt + 1))
        done
        
        echo "❌ Failed after $max_attempts attempts: $description"
        return 1
      }
      
      # =================================================================
      # STEP 1: Create the second database (text2AgentTenants)
      # =================================================================
      echo "📊 Creating text2AgentTenants database..."
      retry_rds_command "Create text2AgentTenants database" \
        "aws rds-data execute-statement \
          --resource-arn '${aws_rds_cluster.main.arn}' \
          --secret-arn '${aws_secretsmanager_secret.db_credentials.arn}' \
          --database '${aws_rds_cluster.main.database_name}' \
          --sql 'CREATE DATABASE \"text2AgentTenants\";' \
          --region ${var.aws_region} \
          --output text >/dev/null 2>&1"

      # =================================================================
      # STEP 2: Initialize str_kb database (Bedrock Knowledge Base)
      # =================================================================
      echo "🧠 Setting up str_kb database for Bedrock..."
      
      # Enable pgvector extension (version 0.5.0+ required for HNSW)
      echo "🔌 Creating vector extension..."
      retry_rds_command "Create vector extension" \
        "aws rds-data execute-statement \
          --resource-arn '${aws_rds_cluster.main.arn}' \
          --secret-arn '${aws_secretsmanager_secret.db_credentials.arn}' \
          --database '${aws_rds_cluster.main.database_name}' \
          --sql 'CREATE EXTENSION IF NOT EXISTS vector;' \
          --region ${var.aws_region} \
          --output text >/dev/null 2>&1"

      # Verify pgvector version (must be 0.5.0+ for HNSW support)
      echo "🔍 Checking pgvector version..."
      retry_rds_command "Check pgvector version" \
        "aws rds-data execute-statement \
          --resource-arn '${aws_rds_cluster.main.arn}' \
          --secret-arn '${aws_secretsmanager_secret.db_credentials.arn}' \
          --database '${aws_rds_cluster.main.database_name}' \
          --sql 'SELECT extname, extversion FROM pg_extension WHERE extname='\''vector'\'';' \
          --region ${var.aws_region} \
          --output text"

      echo "🏗️  Creating bedrock_integration schema..."
      retry_rds_command "Create bedrock_integration schema" \
        "aws rds-data execute-statement \
          --resource-arn '${aws_rds_cluster.main.arn}' \
          --secret-arn '${aws_secretsmanager_secret.db_credentials.arn}' \
          --database '${aws_rds_cluster.main.database_name}' \
          --sql 'CREATE SCHEMA IF NOT EXISTS bedrock_integration;' \
          --region ${var.aws_region} \
          --output text >/dev/null 2>&1"

      # Create Bedrock user with proper permissions (as per AWS docs)
      echo "👤 Creating bedrock_user role..."
      retry_rds_command "Create bedrock_user role" \
        "aws rds-data execute-statement \
          --resource-arn '${aws_rds_cluster.main.arn}' \
          --secret-arn '${aws_secretsmanager_secret.db_credentials.arn}' \
          --database '${aws_rds_cluster.main.database_name}' \
          --sql 'CREATE ROLE bedrock_user LOGIN;' \
          --region ${var.aws_region} \
          --output text >/dev/null 2>&1" || echo "ℹ️  bedrock_user role may already exist"

      # Grant permissions to bedrock_user
      echo "🔐 Granting permissions to bedrock_user..."
      retry_rds_command "Grant schema permissions to bedrock_user" \
        "aws rds-data execute-statement \
          --resource-arn '${aws_rds_cluster.main.arn}' \
          --secret-arn '${aws_secretsmanager_secret.db_credentials.arn}' \
          --database '${aws_rds_cluster.main.database_name}' \
          --sql 'GRANT ALL ON SCHEMA bedrock_integration to bedrock_user;' \
          --region ${var.aws_region} \
          --output text >/dev/null 2>&1"

      # Clean slate approach: Drop existing table if it exists (with wrong structure)
      echo "🧹 Cleaning up any existing table with wrong structure..."
      retry_rds_command "Drop existing table" \
        "aws rds-data execute-statement \
          --resource-arn '${aws_rds_cluster.main.arn}' \
          --secret-arn '${aws_secretsmanager_secret.db_credentials.arn}' \
          --database '${aws_rds_cluster.main.database_name}' \
          --sql 'DROP TABLE IF EXISTS bedrock_integration.bedrock_kb CASCADE;' \
          --region ${var.aws_region} \
          --output text >/dev/null 2>&1" || echo "ℹ️  No existing table to drop"

      # Create table following AWS exact specification
      echo "📋 Creating bedrock_kb table with correct structure..."
      retry_rds_command "Create bedrock_kb table" \
        "aws rds-data execute-statement \
          --resource-arn '${aws_rds_cluster.main.arn}' \
          --secret-arn '${aws_secretsmanager_secret.db_credentials.arn}' \
          --database '${aws_rds_cluster.main.database_name}' \
          --sql 'CREATE TABLE bedrock_integration.bedrock_kb (
            id UUID PRIMARY KEY,
            embedding vector(1024),
            chunks TEXT,
            metadata JSON,
            custom_metadata JSONB
          );' \
          --region ${var.aws_region} \
          --output text >/dev/null 2>&1"

      # Grant table permissions to bedrock_user
      echo "🔐 Granting table permissions to bedrock_user..."
      retry_rds_command "Grant table permissions to bedrock_user" \
        "aws rds-data execute-statement \
          --resource-arn '${aws_rds_cluster.main.arn}' \
          --secret-arn '${aws_secretsmanager_secret.db_credentials.arn}' \
          --database '${aws_rds_cluster.main.database_name}' \
          --sql 'GRANT ALL ON TABLE bedrock_integration.bedrock_kb to bedrock_user;' \
          --region ${var.aws_region} \
          --output text >/dev/null 2>&1"

      # Create the HNSW index for vector similarity search (AWS requirement)
      echo "🎯 Creating HNSW index for vector similarity search..."
      retry_rds_command "Create HNSW index" \
        "aws rds-data execute-statement \
          --resource-arn '${aws_rds_cluster.main.arn}' \
          --secret-arn '${aws_secretsmanager_secret.db_credentials.arn}' \
          --database '${aws_rds_cluster.main.database_name}' \
          --sql 'CREATE INDEX IF NOT EXISTS idx_bedrock_kb_embedding ON bedrock_integration.bedrock_kb USING hnsw (embedding vector_cosine_ops) WITH (ef_construction=256);' \
          --region ${var.aws_region} \
          --output text >/dev/null 2>&1"

      # Verify the index was created successfully
      echo "🔍 Verifying HNSW index creation..."
      retry_rds_command "Verify HNSW index" \
        "aws rds-data execute-statement \
          --resource-arn '${aws_rds_cluster.main.arn}' \
          --secret-arn '${aws_secretsmanager_secret.db_credentials.arn}' \
          --database '${aws_rds_cluster.main.database_name}' \
          --sql 'SELECT indexname, indexdef FROM pg_indexes WHERE tablename = '\''bedrock_kb'\'' AND schemaname = '\''bedrock_integration'\'' AND indexdef LIKE '\''%hnsw%'\'';' \
          --region ${var.aws_region} \
          --output text"

      # Create text search index (AWS requirement)
      echo "📝 Creating text search index..."
      retry_rds_command "Create text search index" \
        "aws rds-data execute-statement \
          --resource-arn '${aws_rds_cluster.main.arn}' \
          --secret-arn '${aws_secretsmanager_secret.db_credentials.arn}' \
          --database '${aws_rds_cluster.main.database_name}' \
          --sql 'CREATE INDEX IF NOT EXISTS idx_bedrock_kb_text ON bedrock_integration.bedrock_kb USING gin (to_tsvector('\''simple'\'', chunks));' \
          --region ${var.aws_region} \
          --output text >/dev/null 2>&1"

      # Create custom metadata index (AWS requirement for filtering)
      echo "🏷️  Creating custom metadata index..."
      retry_rds_command "Create custom metadata index" \
        "aws rds-data execute-statement \
          --resource-arn '${aws_rds_cluster.main.arn}' \
          --secret-arn '${aws_secretsmanager_secret.db_credentials.arn}' \
          --database '${aws_rds_cluster.main.database_name}' \
          --sql 'CREATE INDEX IF NOT EXISTS idx_bedrock_kb_custom_metadata ON bedrock_integration.bedrock_kb USING gin (custom_metadata);' \
          --region ${var.aws_region} \
          --output text >/dev/null 2>&1"



      # =================================================================
      # STEP 3: Initialize text2AgentTenants database (Tenant Management)
      # =================================================================
      echo "🏢 Setting up text2AgentTenants database for tenant management..."
      
      # Enable UUID extension in text2AgentTenants database
      echo "🔧 Creating UUID extension in text2AgentTenants..."
      retry_rds_command "Create UUID extension in text2AgentTenants" \
        "aws rds-data execute-statement \
          --resource-arn '${aws_rds_cluster.main.arn}' \
          --secret-arn '${aws_secretsmanager_secret.db_credentials.arn}' \
          --database 'text2AgentTenants' \
          --sql 'CREATE EXTENSION IF NOT EXISTS \"uuid-ossp\";' \
          --region ${var.aws_region} \
          --output text >/dev/null 2>&1"

      # Create tenantmappings table in text2AgentTenants database
      echo "📊 Creating tenantmappings table..."
      retry_rds_command "Create tenantmappings table" \
        "aws rds-data execute-statement \
          --resource-arn '${aws_rds_cluster.main.arn}' \
          --secret-arn '${aws_secretsmanager_secret.db_credentials.arn}' \
          --database 'text2AgentTenants' \
          --sql 'CREATE TABLE IF NOT EXISTS tenantmappings (
            id SERIAL PRIMARY KEY,
            tenant_id UUID NOT NULL UNIQUE DEFAULT uuid_generate_v4(),
            domain VARCHAR(255) NOT NULL,
            bucket_name VARCHAR(255) NOT NULL,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT unique_domain UNIQUE (domain),
            CONSTRAINT unique_bucket UNIQUE (bucket_name)
          );' \
          --region ${var.aws_region} \
          --output text >/dev/null 2>&1"

      # Create users table in text2AgentTenants database
      echo "👥 Creating users table..."
      retry_rds_command "Create users table" \
        "aws rds-data execute-statement \
          --resource-arn '${aws_rds_cluster.main.arn}' \
          --secret-arn '${aws_secretsmanager_secret.db_credentials.arn}' \
          --database 'text2AgentTenants' \
          --sql 'CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            user_id UUID NOT NULL UNIQUE DEFAULT uuid_generate_v4(),
            email VARCHAR(255) NOT NULL UNIQUE,
            name VARCHAR(255) NOT NULL,
            tenant_id UUID NOT NULL,
            cognito_sub VARCHAR(255) UNIQUE,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT fk_tenant FOREIGN KEY (tenant_id) REFERENCES tenantmappings (tenant_id) ON DELETE CASCADE
          );' \
          --region ${var.aws_region} \
          --output text >/dev/null 2>&1"

      # Create indexes for text2AgentTenants database
      aws rds-data execute-statement \
        --resource-arn "${aws_rds_cluster.main.arn}" \
        --secret-arn "${aws_secretsmanager_secret.db_credentials.arn}" \
        --database "text2AgentTenants" \
        --sql 'CREATE INDEX IF NOT EXISTS idx_tenantmappings_domain ON tenantmappings (domain);' \
        --region ${var.aws_region}

      aws rds-data execute-statement \
        --resource-arn "${aws_rds_cluster.main.arn}" \
        --secret-arn "${aws_secretsmanager_secret.db_credentials.arn}" \
        --database "text2AgentTenants" \
        --sql 'CREATE INDEX IF NOT EXISTS idx_users_email ON users (email);' \
        --region ${var.aws_region}

      aws rds-data execute-statement \
        --resource-arn "${aws_rds_cluster.main.arn}" \
        --secret-arn "${aws_secretsmanager_secret.db_credentials.arn}" \
        --database "text2AgentTenants" \
        --sql 'CREATE INDEX IF NOT EXISTS idx_users_tenant_id ON users (tenant_id);' \
        --region ${var.aws_region}

      aws rds-data execute-statement \
        --resource-arn "${aws_rds_cluster.main.arn}" \
        --secret-arn "${aws_secretsmanager_secret.db_credentials.arn}" \
        --database "text2AgentTenants" \
        --sql 'CREATE INDEX IF NOT EXISTS idx_users_cognito_sub ON users (cognito_sub);' \
        --region ${var.aws_region}

      # Create update trigger function in text2AgentTenants database
      aws rds-data execute-statement \
        --resource-arn "${aws_rds_cluster.main.arn}" \
        --secret-arn "${aws_secretsmanager_secret.db_credentials.arn}" \
        --database "text2AgentTenants" \
        --sql 'CREATE OR REPLACE FUNCTION update_updated_at_column() RETURNS TRIGGER AS $$ BEGIN NEW.updated_at = CURRENT_TIMESTAMP; RETURN NEW; END; $$ language '"'"'plpgsql'"'"';' \
        --region ${var.aws_region}

      # Drop existing triggers in text2AgentTenants database (ignore errors)
      aws rds-data execute-statement \
        --resource-arn "${aws_rds_cluster.main.arn}" \
        --secret-arn "${aws_secretsmanager_secret.db_credentials.arn}" \
        --database "text2AgentTenants" \
        --sql 'DROP TRIGGER IF EXISTS update_tenantmappings_updated_at ON tenantmappings;' \
        --region ${var.aws_region} || true

      aws rds-data execute-statement \
        --resource-arn "${aws_rds_cluster.main.arn}" \
        --secret-arn "${aws_secretsmanager_secret.db_credentials.arn}" \
        --database "text2AgentTenants" \
        --sql 'DROP TRIGGER IF EXISTS update_users_updated_at ON users;' \
        --region ${var.aws_region} || true

      # Create triggers in text2AgentTenants database
      aws rds-data execute-statement \
        --resource-arn "${aws_rds_cluster.main.arn}" \
        --secret-arn "${aws_secretsmanager_secret.db_credentials.arn}" \
        --database "text2AgentTenants" \
        --sql 'CREATE TRIGGER update_tenantmappings_updated_at BEFORE UPDATE ON tenantmappings FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();' \
        --region ${var.aws_region}

      aws rds-data execute-statement \
        --resource-arn "${aws_rds_cluster.main.arn}" \
        --secret-arn "${aws_secretsmanager_secret.db_credentials.arn}" \
        --database "text2AgentTenants" \
        --sql 'CREATE TRIGGER update_users_updated_at BEFORE UPDATE ON users FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();' \
        --region ${var.aws_region}

      echo "✅ Database setup complete!"
      echo "✅ str_kb database: Bedrock Knowledge Base with vector support"
      echo "✅ text2AgentTenants database: Multi-tenant user management"

      # Final validation - ensure table and index exist and are ready
      echo "🔍 Final validation: Checking table and index existence..."
      aws rds-data execute-statement \
        --resource-arn "${aws_rds_cluster.main.arn}" \
        --secret-arn "${aws_secretsmanager_secret.db_credentials.arn}" \
        --database "${aws_rds_cluster.main.database_name}" \
        --sql "SELECT table_name, column_name, data_type FROM information_schema.columns WHERE table_schema = 'bedrock_integration' AND table_name = 'bedrock_kb' AND column_name = 'embedding';" \
        --region ${var.aws_region}

      echo "🔍 Verifying HNSW index is accessible..."
      aws rds-data execute-statement \
        --resource-arn "${aws_rds_cluster.main.arn}" \
        --secret-arn "${aws_secretsmanager_secret.db_credentials.arn}" \
        --database "${aws_rds_cluster.main.database_name}" \
        --sql "SELECT COUNT(*) as index_count FROM pg_indexes WHERE tablename = 'bedrock_kb' AND schemaname = 'bedrock_integration' AND indexdef LIKE '%hnsw%';" \
        --region ${var.aws_region}

      echo "✅ All validations complete - ready for Bedrock Knowledge Base creation!"
    EOF
  }

  depends_on = [
    aws_rds_cluster_instance.main,
    aws_secretsmanager_secret_version.db_credentials
  ]
}

# Additional validation resource specifically for Bedrock readiness
resource "null_resource" "bedrock_readiness_check" {
  # This resource specifically validates that everything is ready for Bedrock
  triggers = {
    schema_init_id = null_resource.db_schema_init.id
    cluster_arn    = aws_rds_cluster.main.arn
  }

  # Extended validation specifically for GitHub Actions
  provisioner "local-exec" {
    command = <<-EOF
      echo "🔍 BEDROCK READINESS CHECK - Final validation before Knowledge Base creation"
      
      # Database is already verified ready from previous step
      echo "⏱️  Database readiness already confirmed - proceeding with validation"

      # Test 1: Verify table exists and has correct structure
      echo "🔍 Test 1: Verifying table structure..."
      TABLE_CHECK=$(aws rds-data execute-statement \
        --resource-arn "${aws_rds_cluster.main.arn}" \
        --secret-arn "${aws_secretsmanager_secret.db_credentials.arn}" \
        --database "${aws_rds_cluster.main.database_name}" \
        --sql "SELECT column_name, data_type FROM information_schema.columns WHERE table_schema = 'bedrock_integration' AND table_name = 'bedrock_kb' ORDER BY column_name;" \
        --region ${var.aws_region} \
        --output text 2>/dev/null || echo "FAILED")
      
      if echo "$TABLE_CHECK" | grep -q "embedding" && echo "$TABLE_CHECK" | grep -q "chunks" && echo "$TABLE_CHECK" | grep -q "metadata"; then
        echo "✅ Table structure verified"
      else
        echo "❌ Table structure validation failed"
        exit 1
      fi

      # Test 2: Verify HNSW index exists
      echo "🔍 Test 2: Verifying HNSW index..."
      INDEX_CHECK=$(aws rds-data execute-statement \
        --resource-arn "${aws_rds_cluster.main.arn}" \
        --secret-arn "${aws_secretsmanager_secret.db_credentials.arn}" \
        --database "${aws_rds_cluster.main.database_name}" \
        --sql "SELECT indexname FROM pg_indexes WHERE tablename = 'bedrock_kb' AND schemaname = 'bedrock_integration' AND indexdef LIKE '%hnsw%' AND indexdef LIKE '%vector_cosine_ops%';" \
        --region ${var.aws_region} \
        --output text 2>/dev/null || echo "FAILED")
      
      if echo "$INDEX_CHECK" | grep -q "idx_bedrock_kb_embedding"; then
        echo "✅ HNSW index verified"
      else
        echo "❌ HNSW index validation failed"
        exit 1
      fi

      # Test 3: Try to access the table as if we're Bedrock
      echo "🔍 Test 3: Testing table accessibility..."
      ACCESS_CHECK=$(aws rds-data execute-statement \
        --resource-arn "${aws_rds_cluster.main.arn}" \
        --secret-arn "${aws_secretsmanager_secret.db_credentials.arn}" \
        --database "${aws_rds_cluster.main.database_name}" \
        --sql "SELECT COUNT(*) FROM bedrock_integration.bedrock_kb;" \
        --region ${var.aws_region} \
        --output text 2>/dev/null || echo "FAILED")
      
      if [ "$ACCESS_CHECK" != "FAILED" ]; then
        echo "✅ Table access verified"
      else
        echo "❌ Table access validation failed"
        exit 1
      fi

      echo "🎉 ALL BEDROCK READINESS CHECKS PASSED - Knowledge Base can now be created safely!"
    EOF
  }

  depends_on = [
    null_resource.db_schema_init
  ]
}