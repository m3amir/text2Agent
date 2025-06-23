# Cognito User Pool
resource "aws_cognito_user_pool" "main" {
  name = "${var.project_name}-${var.environment}-user-pool"

  # User attributes
  alias_attributes = ["email"]
  auto_verified_attributes = ["email"]

  # Custom attributes
  schema {
    attribute_data_type = "String"
    name                = "user_tier"
    mutable             = true
    
    string_attribute_constraints {
      min_length = 1
      max_length = 50
    }
  }

  # Password policy
  password_policy {
    minimum_length    = 8
    require_lowercase = true
    require_numbers   = true
    require_symbols   = true
    require_uppercase = true
  }

  # Email configuration
  email_configuration {
    email_sending_account = "COGNITO_DEFAULT"
  }

  # User verification
  verification_message_template {
    default_email_option = "CONFIRM_WITH_CODE"
    email_subject        = "Your verification code for ${var.project_name}"
    email_message        = "Your verification code is {####}"
  }

  # Lambda triggers
  lambda_config {
    post_confirmation = aws_lambda_function.post_confirmation.arn
  }

  # Account recovery
  account_recovery_setting {
    recovery_mechanism {
      name     = "verified_email"
      priority = 1
    }
  }

  # User pool add-ons
  user_pool_add_ons {
    advanced_security_mode = "ENFORCED"
  }

  tags = {
    Name = "${var.project_name}-${var.environment}-user-pool"
  }

  depends_on = [aws_lambda_function.post_confirmation]
}

# Cognito User Pool Client
resource "aws_cognito_user_pool_client" "main" {
  name         = "${var.project_name}-${var.environment}-user-pool-client"
  user_pool_id = aws_cognito_user_pool.main.id

  # Authentication flows
  explicit_auth_flows = [
    "ALLOW_USER_PASSWORD_AUTH",
    "ALLOW_USER_SRP_AUTH",
    "ALLOW_REFRESH_TOKEN_AUTH"
  ]

  # Token validity
  access_token_validity  = 60    # 1 hour
  id_token_validity     = 60    # 1 hour
  refresh_token_validity = 30   # 30 days

  token_validity_units {
    access_token  = "minutes"
    id_token      = "minutes" 
    refresh_token = "days"
  }

  # Prevent user existence errors
  prevent_user_existence_errors = "ENABLED"

  # OAuth settings
  supported_identity_providers = ["COGNITO"]
  
  callback_urls = [
    "https://localhost:3000/callback",
    "https://${var.project_name}-${var.environment}.example.com/callback"
  ]
  
  logout_urls = [
    "https://localhost:3000/logout",
    "https://${var.project_name}-${var.environment}.example.com/logout"
  ]

  allowed_oauth_flows = ["code", "implicit"]
  allowed_oauth_scopes = ["email", "openid", "profile"]
  allowed_oauth_flows_user_pool_client = true

  # Read and write attributes
  read_attributes = [
    "email",
    "email_verified",
    "preferred_username",
    "custom:user_tier"
  ]

  write_attributes = [
    "email", 
    "preferred_username",
    "custom:user_tier"
  ]
}

# Cognito User Pool Domain
resource "aws_cognito_user_pool_domain" "main" {
  domain       = "${var.project_name}-${var.environment}-${random_string.cognito_domain_suffix.result}"
  user_pool_id = aws_cognito_user_pool.main.id
}

# Random string for unique domain name
resource "random_string" "cognito_domain_suffix" {
  length  = 8
  special = false
  upper   = false
} 