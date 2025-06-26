# =====================================================
# INFRASTRUCTURE OUTPUTS
# Complete text2Agent infrastructure outputs
# =====================================================

# VPC and Networking Outputs
output "vpc_id" {
  description = "ID of the VPC"
  value       = aws_vpc.main.id
}

output "vpc_cidr_block" {
  description = "CIDR block of the VPC"
  value       = aws_vpc.main.cidr_block
}

output "private_subnet_ids" {
  description = "IDs of the private subnets"
  value       = aws_subnet.private[*].id
}

# Aurora Database Outputs
output "aurora_cluster_id" {
  description = "Aurora cluster identifier"
  value       = aws_rds_cluster.aurora.cluster_identifier
}

output "aurora_cluster_arn" {
  description = "Aurora cluster ARN"
  value       = aws_rds_cluster.aurora.arn
}

output "aurora_cluster_endpoint" {
  description = "Aurora cluster endpoint"
  value       = aws_rds_cluster.aurora.endpoint
}

output "aurora_instance_id" {
  description = "Aurora instance identifier"
  value       = aws_rds_cluster_instance.aurora.identifier
}

output "aurora_instance_endpoint" {
  description = "Aurora instance endpoint"
  value       = aws_rds_cluster_instance.aurora.endpoint
}

output "aurora_database_name" {
  description = "Aurora database name"
  value       = aws_rds_cluster.aurora.database_name
}

# S3 Storage Outputs
output "s3_bucket_name" {
  description = "Name of the S3 bucket for documents"
  value       = aws_s3_bucket.documents.bucket
}

output "s3_bucket_arn" {
  description = "ARN of the S3 bucket for documents"
  value       = aws_s3_bucket.documents.arn
}

output "s3_bucket_region" {
  description = "Region of the S3 bucket"
  value       = aws_s3_bucket.documents.region
}

# Bedrock Knowledge Base Outputs
output "bedrock_knowledge_base_id" {
  description = "Bedrock Knowledge Base ID"
  value       = aws_bedrockagent_knowledge_base.main.id
}

output "bedrock_knowledge_base_arn" {
  description = "Bedrock Knowledge Base ARN"
  value       = aws_bedrockagent_knowledge_base.main.arn
}

output "bedrock_knowledge_base_name" {
  description = "Bedrock Knowledge Base name"
  value       = aws_bedrockagent_knowledge_base.main.name
}

output "bedrock_data_source_id" {
  description = "Bedrock S3 Data Source ID"
  value       = aws_bedrockagent_data_source.s3.data_source_id
}

# Cognito Authentication Outputs
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

# Lambda Function Outputs
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

# IAM Outputs
output "bedrock_kb_role_arn" {
  description = "Bedrock Knowledge Base IAM role ARN"
  value       = aws_iam_role.bedrock_kb_role.arn
}

# Security Groups Outputs
output "aurora_security_group_id" {
  description = "Aurora security group ID"
  value       = aws_security_group.aurora.id
}

output "lambda_security_group_id" {
  description = "Lambda security group ID"
  value       = module.auth.lambda_security_group_id
}

# Project Information
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

# Infrastructure Summary
output "infrastructure_summary" {
  description = "Summary of deployed infrastructure"
  value = {
    vpc_id                 = aws_vpc.main.id
    aurora_cluster         = aws_rds_cluster.aurora.cluster_identifier
    aurora_instance        = aws_rds_cluster_instance.aurora.identifier
    s3_bucket              = aws_s3_bucket.documents.bucket
    bedrock_knowledge_base = aws_bedrockagent_knowledge_base.main.name
    cognito_user_pool      = module.auth.cognito_user_pool_id
    lambda_function        = module.auth.post_confirmation_lambda_name
    bedrock_kb_id          = aws_bedrockagent_knowledge_base.main.id
    bedrock_data_source_id = aws_bedrockagent_data_source.s3.data_source_id
  }
} 