# Random string for Cognito domain
resource "random_string" "cognito_domain_suffix" {
  length  = 8
  special = false
  upper   = false
}

# IAM Role for Lambda Functions
resource "aws_iam_role" "lambda_execution_role" {
  name = "${var.project_name}-${var.environment}-lambda-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = "lambda.amazonaws.com"
      }
    }]
  })

  tags = {
    Name = "${var.project_name}-${var.environment}-lambda-role"
  }
}

resource "aws_iam_role_policy_attachment" "lambda_basic_execution" {
  role       = aws_iam_role.lambda_execution_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

# CloudWatch Log Group will be created automatically by Lambda with default settings

# Additional IAM policy for S3 access (if needed for bucket operations)
resource "aws_iam_role_policy" "lambda_s3_policy" {
  name = "${var.project_name}-${var.environment}-lambda-s3-policy"
  role = aws_iam_role.lambda_execution_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:ListAllMyBuckets"
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "s3:CreateBucket",
          "s3:HeadBucket",
          "s3:GetBucketLocation",
          "s3:PutBucketPublicAccessBlock",
          "s3:PutBucketVersioning",
          "s3:GetBucketAcl",
          "s3:PutBucketAcl"
        ]
        Resource = [
          "arn:aws:s3:::text2agent-*",
          "arn:aws:s3:::tenant-*"
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "s3:PutObject",
          "s3:GetObject",
          "s3:ListBucket"
        ]
        Resource = [
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
          "secretsmanager:GetSecretValue"
        ]
        Resource = [
          "arn:aws:secretsmanager:${var.aws_region}:*:secret:rds!db-*"
        ]
      }
    ]
  })
}

# Post Confirmation Lambda for Cognito
resource "aws_lambda_function" "post_confirmation" {
  filename      = var.lambda_zip_path
  function_name = "text2Agent-Post-Confirmation"
  role          = aws_iam_role.lambda_execution_role.arn
  handler       = "index.lambda_handler"
  runtime       = "python3.11"
  timeout       = 60

  environment {
    variables = {
      ENVIRONMENT = var.environment
      PROJECT     = var.project_name
      FUNCTION    = "post-confirmation"
      Tenent_db   = var.database_host
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