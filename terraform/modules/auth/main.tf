# Random string for unique Cognito domain
# VPC configuration passed from main module

resource "random_string" "cognito_domain_suffix" {
  length  = 8
  special = false
  upper   = false
}

# IAM Role for Lambda Execution
resource "aws_iam_role" "lambda_execution_role" {
  name = "${var.project_name}-${var.environment}-lambda-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      }
    ]
  })

  tags = {
    Name = "${var.project_name}-${var.environment}-lambda-role"
  }
}

# Basic Lambda execution policy attachment
resource "aws_iam_role_policy_attachment" "lambda_basic_execution" {
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
  role       = aws_iam_role.lambda_execution_role.name
}

# IAM policy attachment for Lambda VPC access
resource "aws_iam_role_policy_attachment" "lambda_vpc_execution" {
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaVPCAccessExecutionRole"
  role       = aws_iam_role.lambda_execution_role.name
}

# Additional IAM policy for S3 access
resource "aws_iam_role_policy" "lambda_s3_policy" {
  name = "${var.project_name}-${var.environment}-lambda-s3-policy"
  role = aws_iam_role.lambda_execution_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:CreateBucket",
          "s3:GetBucketLocation",
          "s3:ListBucket",
          "s3:GetObject",
          "s3:PutObject",
          "s3:DeleteObject",
          "s3:GetBucketPolicy",
          "s3:PutBucketPolicy",
          "s3:GetBucketAcl",
          "s3:PutBucketAcl",
          "s3:HeadBucket",
          "s3:PutBucketPublicAccessBlock",
          "s3:PutBucketVersioning"
        ]
        Resource = [
          "arn:aws:s3:::${var.project_name}-*",
          "arn:aws:s3:::${var.project_name}-*/*",
          "arn:aws:s3:::text2agent-*",
          "arn:aws:s3:::text2agent-*/*",
          "arn:aws:s3:::tenant-*",
          "arn:aws:s3:::tenant-*/*"
        ]
      }
    ]
  })
}

# Additional IAM policy for Secrets Manager access (for database credentials)
resource "aws_iam_role_policy" "lambda_secrets_policy" {
  name = "${var.project_name}-${var.environment}-lambda-secrets-policy"
  role = aws_iam_role.lambda_execution_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "secretsmanager:GetSecretValue",
          "secretsmanager:DescribeSecret"
        ]
        Resource = [
          # Custom secret we created
          "arn:aws:secretsmanager:${var.aws_region}:*:secret:${var.project_name}-${var.environment}-db-credentials-*",
          # RDS-managed secrets (automatically created by RDS)
          "arn:aws:secretsmanager:${var.aws_region}:*:secret:rds!*"
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "secretsmanager:ListSecrets"
        ]
        Resource = "*"
      }
    ]
  })
}

# Lambda Layer for psycopg2 (PostgreSQL adapter)
resource "aws_lambda_layer_version" "psycopg2_layer" {
  filename                 = "psycopg2-layer.zip"
  layer_name               = "${var.project_name}-${var.environment}-psycopg2-layer"
  description              = "psycopg2 library for PostgreSQL connectivity - Python 3.11 ARM64 Linux compatible v2.9.9"
  compatible_architectures = ["arm64"]
  source_code_hash         = filebase64sha256("psycopg2-layer.zip")

  compatible_runtimes = ["python3.11", "python3.12"]
}

# RDS security group ID passed from main module

# Lambda Security Group for VPC access
resource "aws_security_group" "lambda_sg" {
  name_prefix = "${var.project_name}-${var.environment}-lambda-"
  vpc_id      = var.vpc_id

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "${var.project_name}-${var.environment}-lambda-sg"
  }
}

# Security Group Rule: Allow Lambda to access RDS
resource "aws_security_group_rule" "lambda_to_rds" {
  type                     = "ingress"
  from_port                = 5432
  to_port                  = 5432
  protocol                 = "tcp"
  source_security_group_id = aws_security_group.lambda_sg.id
  security_group_id        = var.rds_security_group_id
  description              = "Allow Lambda access to RDS PostgreSQL"
}

# Post Confirmation Lambda for Cognito
resource "aws_lambda_function" "post_confirmation" {
  filename         = var.lambda_zip_path
  function_name    = "text2Agent-Post-Confirmation"
  role             = aws_iam_role.lambda_execution_role.arn
  handler          = "index.lambda_handler"
  runtime          = "python3.11"
  timeout          = 120
  architectures    = ["arm64"]
  description      = "PostConfirmation trigger with Linux-compatible psycopg2 layer"
  source_code_hash = filebase64sha256(var.lambda_zip_path)

  # Add the psycopg2 layer
  layers = [aws_lambda_layer_version.psycopg2_layer.arn]

  # VPC Configuration for RDS access
  vpc_config {
    subnet_ids         = var.private_subnet_ids
    security_group_ids = [aws_security_group.lambda_sg.id]
  }

  environment {
    variables = {
      ENVIRONMENT    = var.environment
      PROJECT        = var.project_name
      FUNCTION       = "post-confirmation"
      Tenent_db      = var.database_host
      DB_SECRET_NAME = "${var.project_name}-${var.environment}-db-credentials-v2"
      DB_REGION      = var.aws_region
    }
  }

  tags = {
    Name = "text2Agent-Post-Confirmation"
  }

  depends_on = [
    aws_iam_role_policy_attachment.lambda_basic_execution
  ]
}

# Cognito User Pool
resource "aws_cognito_user_pool" "main" {
  name                     = "${var.project_name}-${var.environment}-user-pool"
  username_attributes      = ["email"]
  auto_verified_attributes = ["email"]

  # Standard attributes for name and email
  schema {
    attribute_data_type = "String"
    name                = "email"
    required            = true
    mutable             = true
  }

  schema {
    attribute_data_type = "String"
    name                = "name"
    required            = true
    mutable             = true
    string_attribute_constraints {
      min_length = 1
      max_length = 256
    }
  }

  # Custom attribute for user tier
  schema {
    attribute_data_type = "String"
    name                = "user_tier"
    mutable             = true
    string_attribute_constraints {
      min_length = 1
      max_length = 50
    }
  }

  password_policy {
    minimum_length    = 8
    require_lowercase = true
    require_numbers   = true
    require_symbols   = true
    require_uppercase = true
  }

  email_configuration {
    email_sending_account = "COGNITO_DEFAULT"
  }

  verification_message_template {
    default_email_option = "CONFIRM_WITH_CODE"
    email_subject        = "Your verification code for ${var.project_name}"
    email_message        = "Your verification code is {####}"
  }

  lambda_config {
    post_confirmation = aws_lambda_function.post_confirmation.arn
  }

  account_recovery_setting {
    recovery_mechanism {
      name     = "verified_email"
      priority = 1
    }
  }

  user_pool_add_ons {
    advanced_security_mode = "ENFORCED"
  }

  tags = {
    Name = "${var.project_name}-${var.environment}-user-pool"
  }
}

# Cognito User Pool Client
resource "aws_cognito_user_pool_client" "main" {
  name         = "${var.project_name}-${var.environment}-user-pool-client"
  user_pool_id = aws_cognito_user_pool.main.id

  explicit_auth_flows = [
    "ALLOW_USER_PASSWORD_AUTH",
    "ALLOW_USER_SRP_AUTH",
    "ALLOW_REFRESH_TOKEN_AUTH"
  ]

  access_token_validity  = 60
  id_token_validity      = 60
  refresh_token_validity = 30

  token_validity_units {
    access_token  = "minutes"
    id_token      = "minutes"
    refresh_token = "days"
  }

  prevent_user_existence_errors = "ENABLED"
  supported_identity_providers  = ["COGNITO"]

  callback_urls = [
    "https://localhost:3000/callback",
    "https://${var.project_name}-${var.environment}.example.com/callback"
  ]

  logout_urls = [
    "https://localhost:3000/logout",
    "https://${var.project_name}-${var.environment}.example.com/logout"
  ]

  allowed_oauth_flows                  = ["code", "implicit"]
  allowed_oauth_scopes                 = ["email", "openid", "profile"]
  allowed_oauth_flows_user_pool_client = true

  read_attributes = [
    "email",
    "email_verified",
    "name",
    "preferred_username",
    "custom:user_tier"
  ]

  write_attributes = [
    "email",
    "name",
    "preferred_username",
    "custom:user_tier"
  ]
}

# Cognito User Pool Domain
resource "aws_cognito_user_pool_domain" "main" {
  domain       = "${var.project_name}-${var.environment}-${random_string.cognito_domain_suffix.result}"
  user_pool_id = aws_cognito_user_pool.main.id
}

# Permission for Cognito to invoke Lambda
resource "aws_lambda_permission" "allow_cognito_invoke" {
  statement_id  = "AllowExecutionFromCognito"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.post_confirmation.function_name
  principal     = "cognito-idp.amazonaws.com"
  source_arn    = aws_cognito_user_pool.main.arn
} 