resource "aws_cognito_user_pool" "main" {
  name                     = "${var.project_name}-${var.environment}-user-pool"
  alias_attributes         = ["email"]
  auto_verified_attributes = ["email"]
  
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
    "preferred_username",
    "custom:user_tier"
  ]
  
  write_attributes = [
    "email",
    "preferred_username",
    "custom:user_tier"
  ]
}

resource "random_string" "cognito_domain_suffix" {
  length  = 8
  special = false
  upper   = false
}

resource "aws_cognito_user_pool_domain" "main" {
  domain       = "${var.project_name}-${var.environment}-${random_string.cognito_domain_suffix.result}"
  user_pool_id = aws_cognito_user_pool.main.id
}