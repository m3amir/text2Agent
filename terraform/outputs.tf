# =====================================================
# INFRASTRUCTURE OUTPUTS
# Complete text2Agent infrastructure outputs
# =====================================================

# ==============================================================================
# TEXT2AGENT INFRASTRUCTURE OUTPUTS - MODULAR DEPLOYMENT
# Complete infrastructure outputs sourced from modules
# ==============================================================================

# ==============================================================================
# NETWORKING OUTPUTS
# ==============================================================================

output "vpc_id" {
  description = "ID of the VPC"
  value       = module.networking.vpc_id
}

output "vpc_cidr_block" {
  description = "CIDR block of the VPC"
  value       = module.networking.vpc_cidr_block
}

output "private_subnet_ids" {
  description = "IDs of the private subnets"
  value       = module.networking.private_subnet_ids
}

output "public_subnet_ids" {
  description = "IDs of the public subnets"
  value       = module.networking.public_subnet_ids
}

# ==============================================================================
# DATABASE OUTPUTS
# ==============================================================================

output "aurora_cluster_id" {
  description = "Aurora cluster identifier"
  value       = module.database.cluster_identifier
}

output "aurora_cluster_arn" {
  description = "Aurora cluster ARN"
  value       = module.database.cluster_arn
}

output "aurora_cluster_endpoint" {
  description = "Aurora cluster endpoint"
  value       = module.database.cluster_endpoint
}

output "aurora_database_name" {
  description = "Aurora primary database name (str_kb)"
  value       = module.database.database_name
}

output "aurora_tenants_database_name" {
  description = "Aurora tenants database name"
  value       = module.database.tenants_database_name
}

output "aurora_master_username" {
  description = "Aurora master username"
  value       = module.database.master_username
  sensitive   = true
}

output "aurora_port" {
  description = "Aurora port"
  value       = module.database.port
}

output "aurora_secret_arn" {
  description = "ARN of the Secrets Manager secret containing database credentials"
  value       = module.database.secret_arn
}

output "aurora_secret_name" {
  description = "Name of the Secrets Manager secret containing database credentials"
  value       = module.database.secret_name
}

output "aurora_security_group_id" {
  description = "Aurora security group ID"
  value       = module.database.rds_security_group_id
}

# ==============================================================================
# STORAGE OUTPUTS
# ==============================================================================

output "s3_bucket_name" {
  description = "Name of the S3 bucket for documents"
  value       = module.storage.s3_bucket_name
}

output "s3_bucket_arn" {
  description = "ARN of the S3 bucket for documents"
  value       = module.storage.s3_bucket_arn
}

output "s3_bucket_domain_name" {
  description = "Domain name of the S3 bucket"
  value       = module.storage.s3_bucket_domain_name
}

output "s3_bucket_regional_domain_name" {
  description = "Regional domain name of the S3 bucket"
  value       = module.storage.s3_bucket_regional_domain_name
}

# ==============================================================================
# AI/BEDROCK OUTPUTS
# ==============================================================================

output "bedrock_knowledge_base_id" {
  description = "Bedrock Knowledge Base ID"
  value       = module.ai.knowledge_base_id
}

output "bedrock_knowledge_base_arn" {
  description = "Bedrock Knowledge Base ARN"
  value       = module.ai.knowledge_base_arn
}

output "bedrock_data_source_id" {
  description = "Bedrock S3 Data Source ID"
  value       = module.ai.data_source_id
}

output "bedrock_service_role_arn" {
  description = "Bedrock service role ARN"
  value       = module.ai.bedrock_service_role_arn
}

output "embedding_model_arn" {
  description = "ARN of the embedding model"
  value       = module.ai.embedding_model_arn
}

# ==============================================================================
# SECURITY OUTPUTS
# ==============================================================================

output "app_secrets_arn" {
  description = "ARN of the application secrets"
  value       = module.security.app_secrets_arn
}

output "app_secrets_name" {
  description = "Name of the application secrets"
  value       = module.security.app_secrets_name
}

output "enhanced_monitoring_role_arn" {
  description = "ARN of the enhanced monitoring IAM role"
  value       = module.security.enhanced_monitoring_role_arn
}

# ==============================================================================
# AUTH OUTPUTS
# ==============================================================================

output "cognito_user_pool_id" {
  description = "Cognito User Pool ID"
  value       = module.auth.cognito_user_pool_id
}

output "cognito_user_pool_arn" {
  description = "Cognito User Pool ARN"
  value       = module.auth.cognito_user_pool_arn
}

output "cognito_user_pool_client_id" {
  description = "Cognito User Pool Client ID"
  value       = module.auth.cognito_user_pool_client_id
}

output "cognito_user_pool_domain" {
  description = "Cognito User Pool Domain"
  value       = module.auth.cognito_user_pool_domain
}

output "cognito_user_pool_endpoint" {
  description = "Cognito User Pool Endpoint"
  value       = module.auth.cognito_user_pool_endpoint
}

output "post_confirmation_lambda_name" {
  description = "Post Confirmation Lambda function name"
  value       = module.auth.post_confirmation_lambda_name
}

output "post_confirmation_lambda_arn" {
  description = "Post Confirmation Lambda function ARN"
  value       = module.auth.post_confirmation_lambda_arn
}

output "lambda_role_arn" {
  description = "Lambda execution role ARN"
  value       = module.auth.lambda_role_arn
}

output "lambda_role_name" {
  description = "Lambda execution role name"
  value       = module.auth.lambda_role_name
}

output "lambda_security_group_id" {
  description = "Lambda security group ID"
  value       = module.auth.lambda_security_group_id
}

# ==============================================================================
# PROJECT INFORMATION
# ==============================================================================

output "project_name" {
  description = "Project name"
  value       = var.project_name
}

output "environment" {
  description = "Environment name"
  value       = var.environment
}

output "aws_region" {
  description = "AWS region"
  value       = var.aws_region
}

# ==============================================================================
# INFRASTRUCTURE SUMMARY
# ==============================================================================

output "infrastructure_summary" {
  description = "Summary of deployed infrastructure"
  value = {
    # Networking
    vpc_id          = module.networking.vpc_id
    private_subnets = module.networking.private_subnet_ids
    public_subnets  = module.networking.public_subnet_ids

    # Database
    aurora_cluster  = module.database.cluster_identifier
    aurora_endpoint = module.database.cluster_endpoint

    # Storage
    s3_bucket = module.storage.s3_bucket_name

    # AI/Bedrock
    knowledge_base_id = module.ai.knowledge_base_id
    data_source_id    = module.ai.data_source_id

    # Authentication
    cognito_user_pool = module.auth.cognito_user_pool_id
    lambda_function   = module.auth.post_confirmation_lambda_name

    # Environment
    project_name = var.project_name
    environment  = var.environment
    aws_region   = var.aws_region
  }
} 