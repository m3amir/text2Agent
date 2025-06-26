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
  cluster_identifier = "${var.project_name}-${var.environment}-main"
  engine             = "aurora-postgresql"
  engine_version     = "16.6"
  engine_mode        = "provisioned"
  database_name      = "postgres"
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

  # Wait for the database to be ready
  provisioner "local-exec" {
    command = "sleep 120"
  }

  # Initialize database schema using AWS CLI and RDS Data API
  provisioner "local-exec" {
    command = <<-EOF
      # Execute Bedrock schema initialization step by step
      aws rds-data execute-statement \
        --resource-arn "${aws_rds_cluster.main.arn}" \
        --secret-arn "${aws_secretsmanager_secret.db_credentials.arn}" \
        --database "${aws_rds_cluster.main.database_name}" \
        --sql 'CREATE EXTENSION IF NOT EXISTS vector;' \
        --region ${var.aws_region}

      aws rds-data execute-statement \
        --resource-arn "${aws_rds_cluster.main.arn}" \
        --secret-arn "${aws_secretsmanager_secret.db_credentials.arn}" \
        --database "${aws_rds_cluster.main.database_name}" \
        --sql 'CREATE SCHEMA IF NOT EXISTS bedrock_integration;' \
        --region ${var.aws_region}

      aws rds-data execute-statement \
        --resource-arn "${aws_rds_cluster.main.arn}" \
        --secret-arn "${aws_secretsmanager_secret.db_credentials.arn}" \
        --database "${aws_rds_cluster.main.database_name}" \
        --sql 'CREATE TABLE IF NOT EXISTS bedrock_integration.bedrock_kb (
          id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
          chunks TEXT NOT NULL,
          embedding vector(1024),
          metadata JSONB
        );' \
        --region ${var.aws_region}

      aws rds-data execute-statement \
        --resource-arn "${aws_rds_cluster.main.arn}" \
        --secret-arn "${aws_secretsmanager_secret.db_credentials.arn}" \
        --database "${aws_rds_cluster.main.database_name}" \
        --sql 'CREATE INDEX IF NOT EXISTS idx_bedrock_kb_embedding ON bedrock_integration.bedrock_kb USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);' \
        --region ${var.aws_region}

      aws rds-data execute-statement \
        --resource-arn "${aws_rds_cluster.main.arn}" \
        --secret-arn "${aws_secretsmanager_secret.db_credentials.arn}" \
        --database "${aws_rds_cluster.main.database_name}" \
        --sql 'CREATE INDEX IF NOT EXISTS idx_bedrock_kb_metadata ON bedrock_integration.bedrock_kb USING gin (metadata);' \
        --region ${var.aws_region}

      aws rds-data execute-statement \
        --resource-arn "${aws_rds_cluster.main.arn}" \
        --secret-arn "${aws_secretsmanager_secret.db_credentials.arn}" \
        --database "${aws_rds_cluster.main.database_name}" \
        --sql 'CREATE INDEX IF NOT EXISTS idx_bedrock_kb_chunks_gin ON bedrock_integration.bedrock_kb USING gin (to_tsvector('\''simple'\'', chunks));' \
        --region ${var.aws_region}

      # Create Tenants schema
      aws rds-data execute-statement \
        --resource-arn "${aws_rds_cluster.main.arn}" \
        --secret-arn "${aws_secretsmanager_secret.db_credentials.arn}" \
        --database "${aws_rds_cluster.main.database_name}" \
        --sql 'CREATE SCHEMA IF NOT EXISTS "Tenants";' \
        --region ${var.aws_region}

      # Create tenantmappings table
      aws rds-data execute-statement \
        --resource-arn "${aws_rds_cluster.main.arn}" \
        --secret-arn "${aws_secretsmanager_secret.db_credentials.arn}" \
        --database "${aws_rds_cluster.main.database_name}" \
        --sql 'CREATE TABLE IF NOT EXISTS "Tenants"."tenantmappings" (
          id SERIAL PRIMARY KEY,
          tenant_id UUID NOT NULL UNIQUE,
          domain VARCHAR(255) NOT NULL,
          bucket_name VARCHAR(255) NOT NULL,
          created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
          updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
          CONSTRAINT unique_domain UNIQUE (domain),
          CONSTRAINT unique_bucket UNIQUE (bucket_name)
        );' \
        --region ${var.aws_region}

      # Create users table
      aws rds-data execute-statement \
        --resource-arn "${aws_rds_cluster.main.arn}" \
        --secret-arn "${aws_secretsmanager_secret.db_credentials.arn}" \
        --database "${aws_rds_cluster.main.database_name}" \
        --sql 'CREATE TABLE IF NOT EXISTS "Tenants"."users" (
          id SERIAL PRIMARY KEY,
          user_id UUID NOT NULL UNIQUE,
          email VARCHAR(255) NOT NULL UNIQUE,
          name VARCHAR(255) NOT NULL,
          tenant_id UUID NOT NULL,
          cognito_sub VARCHAR(255) UNIQUE,
          created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
          updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
          CONSTRAINT fk_tenant FOREIGN KEY (tenant_id) REFERENCES "Tenants"."tenantmappings" (tenant_id) ON DELETE CASCADE
        );' \
        --region ${var.aws_region}

      # Create indexes
      aws rds-data execute-statement \
        --resource-arn "${aws_rds_cluster.main.arn}" \
        --secret-arn "${aws_secretsmanager_secret.db_credentials.arn}" \
        --database "${aws_rds_cluster.main.database_name}" \
        --sql 'CREATE INDEX IF NOT EXISTS idx_tenantmappings_domain ON "Tenants"."tenantmappings" (domain);' \
        --region ${var.aws_region}

      aws rds-data execute-statement \
        --resource-arn "${aws_rds_cluster.main.arn}" \
        --secret-arn "${aws_secretsmanager_secret.db_credentials.arn}" \
        --database "${aws_rds_cluster.main.database_name}" \
        --sql 'CREATE INDEX IF NOT EXISTS idx_users_email ON "Tenants"."users" (email);' \
        --region ${var.aws_region}

      aws rds-data execute-statement \
        --resource-arn "${aws_rds_cluster.main.arn}" \
        --secret-arn "${aws_secretsmanager_secret.db_credentials.arn}" \
        --database "${aws_rds_cluster.main.database_name}" \
        --sql 'CREATE INDEX IF NOT EXISTS idx_users_tenant_id ON "Tenants"."users" (tenant_id);' \
        --region ${var.aws_region}

      # Create update trigger function
      aws rds-data execute-statement \
        --resource-arn "${aws_rds_cluster.main.arn}" \
        --secret-arn "${aws_secretsmanager_secret.db_credentials.arn}" \
        --database "${aws_rds_cluster.main.database_name}" \
        --sql 'CREATE OR REPLACE FUNCTION update_updated_at_column() RETURNS TRIGGER AS $$ BEGIN NEW.updated_at = CURRENT_TIMESTAMP; RETURN NEW; END; $$ language '"'"'plpgsql'"'"';' \
        --region ${var.aws_region}

      # Drop existing triggers (ignore errors)
      aws rds-data execute-statement \
        --resource-arn "${aws_rds_cluster.main.arn}" \
        --secret-arn "${aws_secretsmanager_secret.db_credentials.arn}" \
        --database "${aws_rds_cluster.main.database_name}" \
        --sql 'DROP TRIGGER IF EXISTS update_tenantmappings_updated_at ON "Tenants"."tenantmappings";' \
        --region ${var.aws_region} || true

      aws rds-data execute-statement \
        --resource-arn "${aws_rds_cluster.main.arn}" \
        --secret-arn "${aws_secretsmanager_secret.db_credentials.arn}" \
        --database "${aws_rds_cluster.main.database_name}" \
        --sql 'DROP TRIGGER IF EXISTS update_users_updated_at ON "Tenants"."users";' \
        --region ${var.aws_region} || true

      # Create triggers
      aws rds-data execute-statement \
        --resource-arn "${aws_rds_cluster.main.arn}" \
        --secret-arn "${aws_secretsmanager_secret.db_credentials.arn}" \
        --database "${aws_rds_cluster.main.database_name}" \
        --sql 'CREATE TRIGGER update_tenantmappings_updated_at BEFORE UPDATE ON "Tenants"."tenantmappings" FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();' \
        --region ${var.aws_region}

      aws rds-data execute-statement \
        --resource-arn "${aws_rds_cluster.main.arn}" \
        --secret-arn "${aws_secretsmanager_secret.db_credentials.arn}" \
        --database "${aws_rds_cluster.main.database_name}" \
        --sql 'CREATE TRIGGER update_users_updated_at BEFORE UPDATE ON "Tenants"."users" FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();' \
        --region ${var.aws_region}
    EOF
  }

  depends_on = [
    aws_rds_cluster_instance.main,
    aws_secretsmanager_secret_version.db_credentials
  ]
}