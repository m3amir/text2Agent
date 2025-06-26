# =====================================================
# BEDROCK KNOWLEDGE BASE WITH AURORA POSTGRESQL
# Custom implementation using AWS resources directly
# =====================================================

# Create a new VPC for the deployment
data "aws_availability_zones" "available" {
  state = "available"
}

resource "aws_vpc" "main" {
  cidr_block           = "10.0.0.0/16"
  enable_dns_hostnames = true
  enable_dns_support   = true

  tags = {
    Name        = "${var.project_name}-${var.environment}-vpc"
    Project     = var.project_name
    Environment = var.environment
    ManagedBy   = "Terraform"
  }
}

resource "aws_subnet" "private" {
  count             = 2
  vpc_id            = aws_vpc.main.id
  cidr_block        = "10.0.${count.index + 1}.0/24"
  availability_zone = data.aws_availability_zones.available.names[count.index]

  tags = {
    Name        = "${var.project_name}-${var.environment}-private-${count.index + 1}"
    Project     = var.project_name
    Environment = var.environment
    ManagedBy   = "Terraform"
  }
}

resource "aws_db_subnet_group" "main" {
  name       = "${var.project_name}-${var.environment}-db-subnet-group"
  subnet_ids = aws_subnet.private[*].id

  tags = {
    Name        = "${var.project_name}-${var.environment}-db-subnet-group"
    Project     = var.project_name
    Environment = var.environment
    ManagedBy   = "Terraform"
  }
}

# Security group for Aurora
resource "aws_security_group" "aurora" {
  name_prefix = "${var.project_name}-${var.environment}-aurora-"
  vpc_id      = aws_vpc.main.id

  ingress {
    from_port   = 5432
    to_port     = 5432
    protocol    = "tcp"
    cidr_blocks = [aws_vpc.main.cidr_block]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name        = "${var.project_name}-${var.environment}-aurora-sg"
    Project     = var.project_name
    Environment = var.environment
    ManagedBy   = "Terraform"
  }
}

# Aurora PostgreSQL cluster with pgvector
resource "aws_rds_cluster" "aurora" {
  cluster_identifier     = "str-kb"
  engine                 = "aurora-postgresql"
  engine_version         = "16.6"
  database_name          = "bedrock_kb"
  master_username        = "postgres"
  manage_master_user_password = true
  

  db_subnet_group_name   = aws_db_subnet_group.main.name
  vpc_security_group_ids = [aws_security_group.aurora.id]
  
  # Enable Data API for Bedrock
  enable_http_endpoint = true
  
  # Serverless v2 scaling
  serverlessv2_scaling_configuration {
    min_capacity = 0.5
    max_capacity = 2.0
  }
  
  storage_encrypted      = true
  backup_retention_period = 7
  skip_final_snapshot    = var.environment == "dev" ? true : false
  deletion_protection    = var.environment == "prod" ? true : false

  tags = {
    Name        = "str-kb"
    Project     = var.project_name
    Environment = var.environment
    ManagedBy   = "Terraform"
  }
}

# Aurora instance
resource "aws_rds_cluster_instance" "aurora" {
  identifier           = "str-kb-instance"
  cluster_identifier   = aws_rds_cluster.aurora.id
  instance_class       = "db.serverless"
  engine               = aws_rds_cluster.aurora.engine
  engine_version       = aws_rds_cluster.aurora.engine_version
  db_subnet_group_name = aws_db_subnet_group.main.name

  tags = {
    Name        = "str-kb-instance"
    Project     = var.project_name
    Environment = var.environment
    ManagedBy   = "Terraform"
  }
}

# S3 bucket for documents
resource "aws_s3_bucket" "documents" {
  bucket = "str-data-store-bucket"
  
  tags = {
    Project     = var.project_name
    Environment = var.environment
    ManagedBy   = "Terraform"
  }
}

resource "aws_s3_bucket_versioning" "documents" {
  bucket = aws_s3_bucket.documents.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "documents" {
  bucket = aws_s3_bucket.documents.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

# IAM role for Bedrock Knowledge Base
resource "aws_iam_role" "bedrock_kb_role" {
  name = "${var.project_name}-${var.environment}-bedrock-kb-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "bedrock.amazonaws.com"
        }
      }
    ]
  })

  tags = {
    Project     = var.project_name
    Environment = var.environment
    ManagedBy   = "Terraform"
  }
}

# IAM policy for Bedrock Knowledge Base to access Aurora and S3
resource "aws_iam_role_policy" "bedrock_kb_policy" {
  name = "${var.project_name}-${var.environment}-bedrock-kb-policy"
  role = aws_iam_role.bedrock_kb_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "rds-data:BatchExecuteStatement",
          "rds-data:BeginTransaction",
          "rds-data:CommitTransaction",
          "rds-data:ExecuteStatement",
          "rds-data:RollbackTransaction"
        ]
        Resource = aws_rds_cluster.aurora.arn
      },
      {
        Effect = "Allow"
        Action = [
          "rds:DescribeDBClusters",
          "rds:DescribeDBClusterParameters",
          "rds:DescribeDBParameters"
        ]
        Resource = aws_rds_cluster.aurora.arn
      },
      {
        Effect = "Allow"
        Action = [
          "secretsmanager:GetSecretValue",
          "secretsmanager:DescribeSecret"
        ]
        Resource = aws_rds_cluster.aurora.master_user_secret[0].secret_arn
      },
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:ListBucket"
        ]
        Resource = [
          aws_s3_bucket.documents.arn,
          "${aws_s3_bucket.documents.arn}/*"
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "bedrock:InvokeModel"
        ]
        Resource = "arn:aws:bedrock:${var.aws_region}::foundation-model/amazon.titan-embed-text-v2:0"
      }
    ]
  })
}

# Database initialization using AWS RDS Data API
# Note: pgvector is available by default in Aurora PostgreSQL 16.6, no parameter group needed

# Initialize database schema using RDS Data API
resource "null_resource" "init_database" {
  provisioner "local-exec" {
    command = <<-EOF
      # Enable pgvector extension
      aws rds-data execute-statement \
        --resource-arn "${aws_rds_cluster.aurora.arn}" \
        --secret-arn "${aws_rds_cluster.aurora.master_user_secret[0].secret_arn}" \
        --database "${aws_rds_cluster.aurora.database_name}" \
        --sql "CREATE EXTENSION IF NOT EXISTS vector;" \
        --region "${var.aws_region}"

      # Create schema for Bedrock
      aws rds-data execute-statement \
        --resource-arn "${aws_rds_cluster.aurora.arn}" \
        --secret-arn "${aws_rds_cluster.aurora.master_user_secret[0].secret_arn}" \
        --database "${aws_rds_cluster.aurora.database_name}" \
        --sql "CREATE SCHEMA IF NOT EXISTS bedrock_integration;" \
        --region "${var.aws_region}"

      # Create table for Bedrock Knowledge Base
      aws rds-data execute-statement \
        --resource-arn "${aws_rds_cluster.aurora.arn}" \
        --secret-arn "${aws_rds_cluster.aurora.master_user_secret[0].secret_arn}" \
        --database "${aws_rds_cluster.aurora.database_name}" \
        --sql "CREATE TABLE IF NOT EXISTS bedrock_integration.bedrock_kb (
          id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
          chunks TEXT NOT NULL,
          embedding vector(1024),
          metadata JSONB
        );" \
        --region "${var.aws_region}"

      # Create GIN index for full-text search (required by Bedrock)
      aws rds-data execute-statement \
        --resource-arn "${aws_rds_cluster.aurora.arn}" \
        --secret-arn "${aws_rds_cluster.aurora.master_user_secret[0].secret_arn}" \
        --database "${aws_rds_cluster.aurora.database_name}" \
        --sql "CREATE INDEX IF NOT EXISTS bedrock_kb_chunks_gin_idx ON bedrock_integration.bedrock_kb USING gin (to_tsvector('simple', chunks));" \
        --region "${var.aws_region}"

      # Create HNSW index for vector similarity search (required by Bedrock)
      aws rds-data execute-statement \
        --resource-arn "${aws_rds_cluster.aurora.arn}" \
        --secret-arn "${aws_rds_cluster.aurora.master_user_secret[0].secret_arn}" \
        --database "${aws_rds_cluster.aurora.database_name}" \
        --sql "CREATE INDEX IF NOT EXISTS bedrock_kb_embedding_hnsw_idx ON bedrock_integration.bedrock_kb USING hnsw (embedding vector_cosine_ops);" \
        --region "${var.aws_region}"
    EOF
    
    environment = {
      AWS_PROFILE = var.aws_profile
    }
  }
  
  depends_on = [aws_rds_cluster_instance.aurora]
  
  triggers = {
    cluster_arn = aws_rds_cluster.aurora.arn
    secret_arn  = aws_rds_cluster.aurora.master_user_secret[0].secret_arn
    # Force re-run to add HNSW index
    version = "v2"
  }
}

# Bedrock Knowledge Base
resource "aws_bedrockagent_knowledge_base" "main" {
  name        = "${var.project_name}-${var.environment}-kb"
  description = "Knowledge base for ${var.project_name} with Aurora PostgreSQL backend"
  role_arn    = aws_iam_role.bedrock_kb_role.arn

  knowledge_base_configuration {
    vector_knowledge_base_configuration {
      embedding_model_arn = "arn:aws:bedrock:${var.aws_region}::foundation-model/amazon.titan-embed-text-v2:0"
    }
    type = "VECTOR"
  }

  storage_configuration {
    type = "RDS"
    rds_configuration {
      resource_arn    = aws_rds_cluster.aurora.arn
      credentials_secret_arn = aws_rds_cluster.aurora.master_user_secret[0].secret_arn
      database_name   = aws_rds_cluster.aurora.database_name
      table_name      = "bedrock_integration.bedrock_kb"
      field_mapping {
        vector_field   = "embedding"
        text_field     = "chunks"
        metadata_field = "metadata"
        primary_key_field = "id"
      }
    }
  }

  tags = {
    Project     = var.project_name
    Environment = var.environment
    ManagedBy   = "Terraform"
  }

  depends_on = [
    aws_rds_cluster_instance.aurora,
    aws_iam_role_policy.bedrock_kb_policy,
    null_resource.init_database
  ]
}

# S3 Data Source for Knowledge Base
resource "aws_bedrockagent_data_source" "s3" {
  knowledge_base_id = aws_bedrockagent_knowledge_base.main.id
  name              = "${var.project_name}-${var.environment}-s3-datasource"
  description       = "S3 data source for document ingestion"

  data_source_configuration {
    type = "S3"
    s3_configuration {
      bucket_arn = aws_s3_bucket.documents.arn
    }
  }
}

# =====================================================
# AUTH MODULE - COGNITO AND POST CONFIRMATION LAMBDA
# =====================================================

module "auth" {
  source = "./modules/auth"

  project_name         = var.project_name
  environment          = var.environment
  aws_region           = var.aws_region
  lambda_zip_path      = "./post_confirmation.zip"
  database_host        = aws_rds_cluster.aurora.endpoint
  vpc_id               = aws_vpc.main.id
  private_subnet_ids   = aws_subnet.private[*].id
  rds_security_group_id = aws_security_group.aurora.id
}

 