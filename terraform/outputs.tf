# =====================================================
# ROOT OUTPUTS - Expose module outputs
# =====================================================

# Storage Module Outputs
output "s3_bucket_name" {
  description = "Name of the S3 bucket"
  value       = module.storage.s3_bucket_name
}

output "s3_bucket_arn" {
  description = "ARN of the S3 bucket"
  value       = module.storage.s3_bucket_arn
}

output "s3_bucket_domain_name" {
  description = "Domain name of the S3 bucket"
  value       = module.storage.s3_bucket_domain_name
}

# Authentication Module Outputs
output "cognito_user_pool_id" {
  description = "ID of the Cognito User Pool"
  value       = module.auth.cognito_user_pool_id
}

output "cognito_user_pool_arn" {
  description = "ARN of the Cognito User Pool"
  value       = module.auth.cognito_user_pool_arn
}

output "cognito_user_pool_client_id" {
  description = "ID of the Cognito User Pool Client"
  value       = module.auth.cognito_user_pool_client_id
}

output "cognito_user_pool_domain" {
  description = "Domain of the Cognito User Pool"
  value       = module.auth.cognito_user_pool_domain
}

output "post_confirmation_lambda_name" {
  description = "Name of the post confirmation Lambda function"
  value       = module.auth.post_confirmation_lambda_name
}

output "post_confirmation_lambda_arn" {
  description = "ARN of the post confirmation Lambda function"
  value       = module.auth.post_confirmation_lambda_arn
}

output "lambda_role_arn" {
  description = "ARN of the Lambda execution role"
  value       = module.auth.lambda_role_arn
}

# Deployment Information
output "deployment_info" {
  description = "Information about the current deployment"
  value = {
    mode             = "MODULAR - Lambda + Cognito + S3"
    environment      = var.environment
    project          = var.project_name
    region           = var.aws_region
    lambda_count     = 1
    cognito_enabled  = true
    s3_enabled       = true
    triggers_enabled = true
    modules_active   = ["storage", "auth"]
    modules_disabled = ["networking", "database", "security", "ai"]
  }
} 