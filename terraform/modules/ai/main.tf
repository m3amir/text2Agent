# ==============================================================================
# BEDROCK KNOWLEDGE BASE MODULE
# Implements a fully managed RAG solution using Amazon Bedrock Knowledge Base
# with Aurora PostgreSQL as the vector store
# ==============================================================================

# Data source for the embedding model
data "aws_bedrock_foundation_model" "embedding" {
  model_id = "amazon.titan-embed-text-v2:0"
}

# ==============================================================================
# IAM ROLE AND POLICIES FOR BEDROCK KNOWLEDGE BASE
# ==============================================================================

# Service role for Bedrock Knowledge Base
resource "aws_iam_role" "bedrock_kb" {
  name = "${var.project_name}-${var.environment}-bedrock-kb-service-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "bedrock.amazonaws.com"
        }
        Action = "sts:AssumeRole"
      }
    ]
  })

  tags = var.tags
}

# Policy for Bedrock to invoke embedding models
resource "aws_iam_policy" "bedrock_model_invoke" {
  name        = "${var.project_name}-${var.environment}-bedrock-model-invoke"
  description = "Allow Bedrock Knowledge Base to invoke embedding models"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "bedrock:InvokeModel"
        ]
        Resource = [
          data.aws_bedrock_foundation_model.embedding.model_arn
        ]
      }
    ]
  })
}

# Policy for Bedrock to access S3 data source
resource "aws_iam_policy" "bedrock_s3_access" {
  name        = "${var.project_name}-${var.environment}-bedrock-s3-access"
  description = "Allow Bedrock Knowledge Base to access S3 data source"

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
          var.s3_bucket_arn,
          "${var.s3_bucket_arn}/documents/*"
        ]
      }
    ]
  })
}

# Policy for Bedrock to access Aurora PostgreSQL via RDS Data API
resource "aws_iam_policy" "bedrock_rds_access" {
  name        = "${var.project_name}-${var.environment}-bedrock-rds-access"
  description = "Allow Bedrock Knowledge Base to access Aurora PostgreSQL via RDS Data API"

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
        Resource = var.db_cluster_arn
      },
      {
        Effect = "Allow"
        Action = [
          "rds:DescribeDBClusters",
          "rds:DescribeDBInstances"
        ]
        Resource = [
          var.db_cluster_arn,
          "${replace(var.db_cluster_arn, ":cluster:", ":db:")}*"
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "secretsmanager:GetSecretValue",
          "secretsmanager:DescribeSecret"
        ]
        Resource = var.db_master_user_secret_arn
      }
    ]
  })
}

# Attach policies to the Bedrock service role
resource "aws_iam_role_policy_attachment" "bedrock_model_invoke" {
  role       = aws_iam_role.bedrock_kb.name
  policy_arn = aws_iam_policy.bedrock_model_invoke.arn
}

resource "aws_iam_role_policy_attachment" "bedrock_s3_access" {
  role       = aws_iam_role.bedrock_kb.name
  policy_arn = aws_iam_policy.bedrock_s3_access.arn
}

resource "aws_iam_role_policy_attachment" "bedrock_rds_access" {
  role       = aws_iam_role.bedrock_kb.name
  policy_arn = aws_iam_policy.bedrock_rds_access.arn
}

# ==============================================================================
# BEDROCK KNOWLEDGE BASE
# ==============================================================================

resource "aws_bedrockagent_knowledge_base" "main" {
  name     = "${var.project_name}-${var.environment}-kb"
  role_arn = aws_iam_role.bedrock_kb.arn

  knowledge_base_configuration {
    type = "VECTOR"
    vector_knowledge_base_configuration {
      embedding_model_arn = data.aws_bedrock_foundation_model.embedding.model_arn
      embedding_model_configuration {
        bedrock_embedding_model_configuration {
          dimensions = 1024
        }
      }
    }
  }

  storage_configuration {
    type = "RDS"
    rds_configuration {
      credentials_secret_arn = var.db_master_user_secret_arn
      database_name          = var.db_name
      resource_arn           = var.db_cluster_arn
      table_name             = "bedrock_integration.bedrock_kb"

      field_mapping {
        primary_key_field = "id"
        vector_field      = "embedding"
        text_field        = "chunks"
        metadata_field    = "metadata"
      }
    }
  }

  tags = var.tags

  depends_on = [
    aws_iam_role_policy_attachment.bedrock_model_invoke,
    aws_iam_role_policy_attachment.bedrock_s3_access,
    aws_iam_role_policy_attachment.bedrock_rds_access,
    var.db_schema_dependency
  ]
}

# ==============================================================================
# DATA SOURCE FOR KNOWLEDGE BASE
# ==============================================================================

resource "aws_bedrockagent_data_source" "s3_documents" {
  knowledge_base_id = aws_bedrockagent_knowledge_base.main.id
  name              = "${var.project_name}-${var.environment}-s3-data-source"

  data_source_configuration {
    type = "S3"
    s3_configuration {
      bucket_arn         = var.s3_bucket_arn
      inclusion_prefixes = ["documents/"]
    }
  }
}