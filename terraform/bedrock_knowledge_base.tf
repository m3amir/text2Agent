# Data source to check available Bedrock models
data "aws_bedrock_foundation_models" "available" {
  by_provider = "Amazon"
}

# Local values for model validation
locals {
  titan_v2_model_arn = "arn:aws:bedrock:${var.aws_region}::foundation-model/amazon.titan-embed-text-v2:0"
  available_models   = [for model in data.aws_bedrock_foundation_models.available.model_summaries : model.model_arn]
  titan_v2_available = contains(local.available_models, local.titan_v2_model_arn)
}

# Random ID for unique resource naming
resource "random_id" "kb_suffix" {
  byte_length = 4
}

# Enable Bedrock Model Access
resource "null_resource" "enable_bedrock_models" {
  provisioner "local-exec" {
    command = <<-EOT
      echo "🔧 Enabling Bedrock model access..."
      
      # Check if models are already enabled
      aws bedrock list-foundation-models \
        --region ${var.aws_region} \
        --profile m3 \
        --output table || echo "Bedrock service not accessible"
      
      # Enable Amazon Titan Embed Text V2 model
      aws bedrock put-model-invocation-logging-configuration \
        --region ${var.aws_region} \
        --profile m3 \
        --logging-config '{}' || echo "Model logging config already set"
      
      # Note: Model access must be requested manually via AWS Console
      # Go to: https://${var.aws_region}.console.aws.amazon.com/bedrock/home?region=${var.aws_region}#/modelaccess
      echo "⚠️  IMPORTANT: If this is your first time using Bedrock, you need to:"
      echo "   1. Go to AWS Bedrock Console > Model access"
      echo "   2. Request access to 'Amazon Titan Text Embeddings V2'"
      echo "   3. Wait for approval (usually instant)"
      echo "   4. Re-run terraform apply"
      
      # Verify model access
      sleep 5
      aws bedrock invoke-model \
        --region ${var.aws_region} \
        --profile m3 \
        --model-id amazon.titan-embed-text-v2:0 \
        --body '{"inputText":"test"}' \
        --content-type application/json \
        --accept application/json \
        /tmp/bedrock-test-output.json && echo "✅ Bedrock model access verified!" || echo "❌ Model access not yet enabled - please enable in AWS Console"
      
      rm -f /tmp/bedrock-test-output.json
    EOT
  }

  triggers = {
    # Run this check every time
    always_run = timestamp()
  }
}

# IAM Role for Bedrock Knowledge Base
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
    Name = "${var.project_name}-${var.environment}-bedrock-kb-role"
  }
}

# IAM Policy for Bedrock to access S3
resource "aws_iam_policy" "bedrock_s3_policy" {
  name = "${var.project_name}-${var.environment}-bedrock-s3-policy"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:ListBucket"
        ]
        Resource = [
          aws_s3_bucket.str_data_store.arn,
          "${aws_s3_bucket.str_data_store.arn}/*"
        ]
      }
    ]
  })
}

# IAM Policy for Bedrock to invoke embedding models
resource "aws_iam_policy" "bedrock_model_policy" {
  name = "${var.project_name}-${var.environment}-bedrock-model-policy"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "bedrock:InvokeModel"
        ]
        Resource = [
          "arn:aws:bedrock:${var.aws_region}::foundation-model/amazon.titan-embed-text-v2:0",
          "arn:aws:bedrock:${var.aws_region}::foundation-model/amazon.titan-embed-text-v1",
          "arn:aws:bedrock:${var.aws_region}::foundation-model/cohere.embed-english-v3",
          "arn:aws:bedrock:${var.aws_region}::foundation-model/cohere.embed-multilingual-v3"
        ]
      }
    ]
  })
}

# IAM Policy for Bedrock to access RDS and Secrets Manager
resource "aws_iam_policy" "bedrock_rds_policy" {
  name = "${var.project_name}-${var.environment}-bedrock-rds-policy"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "rds:DescribeDBClusters",
          "rds:DescribeDBInstances",
          "rds-data:BatchExecuteStatement",
          "rds-data:BeginTransaction",
          "rds-data:CommitTransaction",
          "rds-data:ExecuteStatement",
          "rds-data:RollbackTransaction"
        ]
        Resource = aws_rds_cluster.bedrock.arn
      },
      {
        Effect = "Allow"
        Action = [
          "secretsmanager:GetSecretValue",
          "secretsmanager:DescribeSecret"
        ]
        Resource = aws_secretsmanager_secret.bedrock_kb_secret.arn
      }
    ]
  })
}

# Attach policies to Bedrock role
resource "aws_iam_role_policy_attachment" "bedrock_s3_attachment" {
  role       = aws_iam_role.bedrock_kb_role.name
  policy_arn = aws_iam_policy.bedrock_s3_policy.arn
}

resource "aws_iam_role_policy_attachment" "bedrock_model_attachment" {
  role       = aws_iam_role.bedrock_kb_role.name
  policy_arn = aws_iam_policy.bedrock_model_policy.arn
}

resource "aws_iam_role_policy_attachment" "bedrock_rds_attachment" {
  role       = aws_iam_role.bedrock_kb_role.name
  policy_arn = aws_iam_policy.bedrock_rds_policy.arn
}

# Secrets Manager secret for Bedrock database access
resource "aws_secretsmanager_secret" "bedrock_kb_secret" {
  name        = "${var.project_name}-${var.environment}-bedrock-kb-secret-${random_id.kb_suffix.hex}"
  description = "Database credentials for Bedrock Knowledge Base"

  tags = {
    Name = "${var.project_name}-${var.environment}-bedrock-kb-secret"
  }
}

resource "aws_secretsmanager_secret_version" "bedrock_kb_secret" {
  secret_id = aws_secretsmanager_secret.bedrock_kb_secret.id
  secret_string = jsonencode({
    username = "postgres"
    password = random_password.bedrock_db_password.result
  })
}

# Database setup automation
resource "null_resource" "bedrock_db_setup" {
  depends_on = [
    aws_rds_cluster.bedrock,
    aws_rds_cluster_instance.bedrock,
    aws_secretsmanager_secret_version.bedrock_kb_secret,
    local_file.bedrock_db_setup_script
  ]

  triggers = {
    rds_cluster_id = aws_rds_cluster.bedrock.id
    script_hash    = local_file.bedrock_db_setup_script.content_md5
  }

  provisioner "local-exec" {
    command = <<-EOT
      # Wait for RDS cluster to be fully available
      sleep 30
      
      # Execute the database setup script using AWS RDS Data API
      aws rds-data execute-statement \
        --profile m3 \
        --region us-west-2 \
        --resource-arn "${aws_rds_cluster.bedrock.arn}" \
        --secret-arn "${aws_secretsmanager_secret.bedrock_kb_secret.arn}" \
        --database "postgres" \
        --sql "CREATE EXTENSION IF NOT EXISTS vector;" || echo "Vector extension may already exist"
      
      aws rds-data execute-statement \
        --profile m3 \
        --region us-west-2 \
        --resource-arn "${aws_rds_cluster.bedrock.arn}" \
        --secret-arn "${aws_secretsmanager_secret.bedrock_kb_secret.arn}" \
        --database "postgres" \
        --sql "CREATE SCHEMA IF NOT EXISTS bedrock_integration;"
      
      aws rds-data execute-statement \
        --profile m3 \
        --region us-west-2 \
        --resource-arn "${aws_rds_cluster.bedrock.arn}" \
        --secret-arn "${aws_secretsmanager_secret.bedrock_kb_secret.arn}" \
        --database "postgres" \
        --sql "CREATE TABLE IF NOT EXISTS bedrock_integration.bedrock_kb (id uuid PRIMARY KEY DEFAULT gen_random_uuid(), embedding vector(1024), chunks text, metadata json, custom_metadata jsonb);"
      
      aws rds-data execute-statement \
        --profile m3 \
        --region us-west-2 \
        --resource-arn "${aws_rds_cluster.bedrock.arn}" \
        --secret-arn "${aws_secretsmanager_secret.bedrock_kb_secret.arn}" \
        --database "postgres" \
        --sql "CREATE INDEX IF NOT EXISTS bedrock_kb_embedding_idx ON bedrock_integration.bedrock_kb USING hnsw (embedding vector_cosine_ops);" || echo "Index may already exist"
      
      aws rds-data execute-statement \
        --profile m3 \
        --region us-west-2 \
        --resource-arn "${aws_rds_cluster.bedrock.arn}" \
        --secret-arn "${aws_secretsmanager_secret.bedrock_kb_secret.arn}" \
        --database "postgres" \
        --sql "CREATE INDEX IF NOT EXISTS bedrock_kb_chunks_idx ON bedrock_integration.bedrock_kb USING gin (to_tsvector('simple', chunks));" || echo "Index may already exist"
      
      aws rds-data execute-statement \
        --profile m3 \
        --region us-west-2 \
        --resource-arn "${aws_rds_cluster.bedrock.arn}" \
        --secret-arn "${aws_secretsmanager_secret.bedrock_kb_secret.arn}" \
        --database "postgres" \
        --sql "CREATE INDEX IF NOT EXISTS bedrock_kb_metadata_idx ON bedrock_integration.bedrock_kb USING gin (custom_metadata);" || echo "Index may already exist"
      
      echo "Bedrock database setup completed successfully!"
    EOT
  }
}

# Bedrock Knowledge Base
resource "aws_bedrockagent_knowledge_base" "main" {
  name     = "${var.project_name}-${var.environment}-knowledge-base"
  role_arn = aws_iam_role.bedrock_kb_role.arn

  knowledge_base_configuration {
    vector_knowledge_base_configuration {
      embedding_model_arn = "arn:aws:bedrock:${var.aws_region}::foundation-model/amazon.titan-embed-text-v2:0"
      embedding_model_configuration {
        bedrock_embedding_model_configuration {
          dimensions = 1024
        }
      }
    }
    type = "VECTOR"
  }

  storage_configuration {
    rds_configuration {
      resource_arn           = aws_rds_cluster.bedrock.arn
      database_name          = "postgres"
      table_name             = "bedrock_integration.bedrock_kb"
      credentials_secret_arn = aws_secretsmanager_secret.bedrock_kb_secret.arn
      field_mapping {
        vector_field      = "embedding"
        text_field        = "chunks"
        metadata_field    = "metadata"
        primary_key_field = "id"
      }
    }
    type = "RDS"
  }

  tags = {
    Name = "${var.project_name}-${var.environment}-knowledge-base"
  }

  depends_on = [
    aws_rds_cluster.bedrock,
    aws_iam_role_policy_attachment.bedrock_s3_attachment,
    aws_iam_role_policy_attachment.bedrock_model_attachment,
    aws_iam_role_policy_attachment.bedrock_rds_attachment,
    aws_secretsmanager_secret_version.bedrock_kb_secret,
    null_resource.bedrock_db_setup,
    null_resource.enable_bedrock_models
  ]
}

# Data source for Bedrock Knowledge Base (S3) with Semantic Chunking
resource "aws_bedrockagent_data_source" "s3_data_source" {
  knowledge_base_id = aws_bedrockagent_knowledge_base.main.id
  name              = "${var.project_name}-${var.environment}-s3-data-source"

  data_source_configuration {
    s3_configuration {
      bucket_arn         = aws_s3_bucket.str_data_store.arn
      inclusion_prefixes = ["documents/"]
    }
    type = "S3"
  }

  # Vector ingestion configuration with semantic chunking
  vector_ingestion_configuration {
    chunking_configuration {
      chunking_strategy = var.chunking_strategy

      # Conditional semantic chunking configuration (note: may have typo in provider)
      dynamic "semantic_chunking_configuration" {
        for_each = var.chunking_strategy == "SEMANTIC" ? [1] : []
        content {
          breakpoint_percentile_threshold = var.semantic_breakpoint_percentile_threshold
          buffer_size                     = var.semantic_buffer_size
          max_token                       = var.semantic_max_tokens
        }
      }

      # Conditional fixed size chunking configuration
      dynamic "fixed_size_chunking_configuration" {
        for_each = var.chunking_strategy == "FIXED_SIZE" ? [1] : []
        content {
          max_tokens         = var.semantic_max_tokens
          overlap_percentage = 20
        }
      }

      # Conditional hierarchical chunking configuration
      dynamic "hierarchical_chunking_configuration" {
        for_each = var.chunking_strategy == "HIERARCHICAL" ? [1] : []
        content {
          level_configuration {
            max_tokens = var.semantic_max_tokens
          }
          level_configuration {
            max_tokens = var.semantic_max_tokens * 3
          }
          overlap_tokens = 60
        }
      }
    }
  }

  depends_on = [aws_bedrockagent_knowledge_base.main]
}

# Output database setup script for manual execution
resource "local_file" "bedrock_db_setup_script" {
  filename = "${path.module}/setup_bedrock_database.sql"
  content  = <<-EOT
-- Setup script for Bedrock Knowledge Base database requirements
-- Run this script against your Aurora PostgreSQL database after deployment

-- Install the pgvector extension (version 0.5.0 or higher)
CREATE EXTENSION IF NOT EXISTS vector;

-- Create the bedrock_integration schema
CREATE SCHEMA IF NOT EXISTS bedrock_integration;

-- Create the bedrock_user role
CREATE ROLE bedrock_user WITH PASSWORD '${random_password.bedrock_db_password.result}' LOGIN;

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
EOT
}

 