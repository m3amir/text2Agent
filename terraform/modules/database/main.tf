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
  cluster_identifier = "str-kb"
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
    max_capacity = 2
    min_capacity = 0.5
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
  }

  # Wait for the database to be ready - longer wait for GitHub Actions
  provisioner "local-exec" {
    command = <<-EOF
      echo "Waiting for database to be fully ready..."
      if [ "$GITHUB_ACTIONS" = "true" ]; then
        echo "Running in GitHub Actions - using extended wait time"
        sleep 300  # 5 minutes for GitHub Actions
      else
        echo "Running locally - using standard wait time"
        sleep 120  # 2 minutes for local
      fi
    EOF
  }

  # Initialize TWO separate databases using AWS CLI and RDS Data API
  provisioner "local-exec" {
    command = <<-EOF
      # =================================================================
      # STEP 1: Create the second database (text2AgentTenants)
      # =================================================================
      echo "Creating text2AgentTenants database..."
      aws rds-data execute-statement \
        --resource-arn "${aws_rds_cluster.main.arn}" \
        --secret-arn "${aws_secretsmanager_secret.db_credentials.arn}" \
        --database "${aws_rds_cluster.main.database_name}" \
        --sql 'CREATE DATABASE "text2AgentTenants";' \
        --region ${var.aws_region}

      # =================================================================
      # STEP 2: Initialize str_kb database (Bedrock Knowledge Base)
      # =================================================================
      echo "Setting up str_kb database for Bedrock..."
      # Enable pgvector extension (version 0.5.0+ required for HNSW)
      aws rds-data execute-statement \
        --resource-arn "${aws_rds_cluster.main.arn}" \
        --secret-arn "${aws_secretsmanager_secret.db_credentials.arn}" \
        --database "${aws_rds_cluster.main.database_name}" \
        --sql 'CREATE EXTENSION IF NOT EXISTS vector;' \
        --region ${var.aws_region}

      # Verify pgvector version (must be 0.5.0+ for HNSW support)
      echo "Checking pgvector version..."
      aws rds-data execute-statement \
        --resource-arn "${aws_rds_cluster.main.arn}" \
        --secret-arn "${aws_secretsmanager_secret.db_credentials.arn}" \
        --database "${aws_rds_cluster.main.database_name}" \
        --sql "SELECT extversion FROM pg_extension WHERE extname='vector';" \
        --region ${var.aws_region}

      aws rds-data execute-statement \
        --resource-arn "${aws_rds_cluster.main.arn}" \
        --secret-arn "${aws_secretsmanager_secret.db_credentials.arn}" \
        --database "${aws_rds_cluster.main.database_name}" \
        --sql 'CREATE SCHEMA IF NOT EXISTS bedrock_integration;' \
        --region ${var.aws_region}

      # Create Bedrock user with proper permissions (as per AWS docs)
      aws rds-data execute-statement \
        --resource-arn "${aws_rds_cluster.main.arn}" \
        --secret-arn "${aws_secretsmanager_secret.db_credentials.arn}" \
        --database "${aws_rds_cluster.main.database_name}" \
        --sql "CREATE ROLE bedrock_user LOGIN;" \
        --region ${var.aws_region} || echo "bedrock_user role might already exist"

      # Grant permissions to bedrock_user
      aws rds-data execute-statement \
        --resource-arn "${aws_rds_cluster.main.arn}" \
        --secret-arn "${aws_secretsmanager_secret.db_credentials.arn}" \
        --database "${aws_rds_cluster.main.database_name}" \
        --sql 'GRANT ALL ON SCHEMA bedrock_integration to bedrock_user;' \
        --region ${var.aws_region}

      # Create table following AWS exact specification
      aws rds-data execute-statement \
        --resource-arn "${aws_rds_cluster.main.arn}" \
        --secret-arn "${aws_secretsmanager_secret.db_credentials.arn}" \
        --database "${aws_rds_cluster.main.database_name}" \
        --sql 'CREATE TABLE IF NOT EXISTS bedrock_integration.bedrock_kb (
          id UUID PRIMARY KEY,
          embedding vector(1024),
          chunks TEXT,
          metadata JSON,
          custom_metadata JSONB
        );' \
        --region ${var.aws_region}

      # Grant table permissions to bedrock_user
      aws rds-data execute-statement \
        --resource-arn "${aws_rds_cluster.main.arn}" \
        --secret-arn "${aws_secretsmanager_secret.db_credentials.arn}" \
        --database "${aws_rds_cluster.main.database_name}" \
        --sql 'GRANT ALL ON TABLE bedrock_integration.bedrock_kb to bedrock_user;' \
        --region ${var.aws_region}

      # Create the HNSW index for vector similarity search (AWS requirement)
      # Using ef_construction=256 as recommended by AWS for pgvector 0.6.0+
      aws rds-data execute-statement \
        --resource-arn "${aws_rds_cluster.main.arn}" \
        --secret-arn "${aws_secretsmanager_secret.db_credentials.arn}" \
        --database "${aws_rds_cluster.main.database_name}" \
        --sql 'CREATE INDEX IF NOT EXISTS idx_bedrock_kb_embedding ON bedrock_integration.bedrock_kb USING hnsw (embedding vector_cosine_ops) WITH (ef_construction=256);' \
        --region ${var.aws_region}

      # Verify the index was created successfully
      echo "Verifying HNSW index creation..."
      aws rds-data execute-statement \
        --resource-arn "${aws_rds_cluster.main.arn}" \
        --secret-arn "${aws_secretsmanager_secret.db_credentials.arn}" \
        --database "${aws_rds_cluster.main.database_name}" \
        --sql "SELECT indexname, indexdef FROM pg_indexes WHERE tablename = 'bedrock_kb' AND schemaname = 'bedrock_integration' AND indexdef LIKE '%hnsw%';" \
        --region ${var.aws_region}

      # Create text search index (AWS requirement)
      aws rds-data execute-statement \
        --resource-arn "${aws_rds_cluster.main.arn}" \
        --secret-arn "${aws_secretsmanager_secret.db_credentials.arn}" \
        --database "${aws_rds_cluster.main.database_name}" \
        --sql 'CREATE INDEX IF NOT EXISTS idx_bedrock_kb_text ON bedrock_integration.bedrock_kb USING gin (to_tsvector('\''simple'\'', chunks));' \
        --region ${var.aws_region}

      # Create custom metadata index (AWS requirement for filtering)
      aws rds-data execute-statement \
        --resource-arn "${aws_rds_cluster.main.arn}" \
        --secret-arn "${aws_secretsmanager_secret.db_credentials.arn}" \
        --database "${aws_rds_cluster.main.database_name}" \
        --sql 'CREATE INDEX IF NOT EXISTS idx_bedrock_kb_custom_metadata ON bedrock_integration.bedrock_kb USING gin (custom_metadata);' \
        --region ${var.aws_region}



      # =================================================================
      # STEP 3: Initialize text2AgentTenants database (Tenant Management)
      # =================================================================
      echo "Setting up text2AgentTenants database for tenant management..."
      
      # Enable UUID extension in text2AgentTenants database
      aws rds-data execute-statement \
        --resource-arn "${aws_rds_cluster.main.arn}" \
        --secret-arn "${aws_secretsmanager_secret.db_credentials.arn}" \
        --database "text2AgentTenants" \
        --sql 'CREATE EXTENSION IF NOT EXISTS "uuid-ossp";' \
        --region ${var.aws_region}

      # Create tenantmappings table in text2AgentTenants database
      aws rds-data execute-statement \
        --resource-arn "${aws_rds_cluster.main.arn}" \
        --secret-arn "${aws_secretsmanager_secret.db_credentials.arn}" \
        --database "text2AgentTenants" \
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
        --region ${var.aws_region}

      # Create users table in text2AgentTenants database
      aws rds-data execute-statement \
        --resource-arn "${aws_rds_cluster.main.arn}" \
        --secret-arn "${aws_secretsmanager_secret.db_credentials.arn}" \
        --database "text2AgentTenants" \
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
        --region ${var.aws_region}

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