# VPC Outputs
output "vpc_id" {
  description = "ID of the VPC"
  value       = aws_vpc.main.id
}

output "vpc_cidr_block" {
  description = "CIDR block of the VPC"
  value       = aws_vpc.main.cidr_block
}

output "public_subnet_ids" {
  description = "IDs of the public subnets"
  value       = aws_subnet.public[*].id
}

output "private_subnet_ids" {
  description = "IDs of the private subnets"
  value       = aws_subnet.private[*].id
}

# STR Data Store S3 Bucket Outputs
output "str_data_store_bucket_id" {
  description = "Name of the STR data store S3 bucket"
  value       = aws_s3_bucket.str_data_store.id
}

output "str_data_store_bucket_arn" {
  description = "ARN of the STR data store S3 bucket"
  value       = aws_s3_bucket.str_data_store.arn
}

output "str_data_store_bucket_domain_name" {
  description = "Domain name of the STR data store S3 bucket"
  value       = aws_s3_bucket.str_data_store.bucket_domain_name
}

output "str_data_store_bucket_regional_domain_name" {
  description = "Regional domain name of the STR data store S3 bucket"
  value       = aws_s3_bucket.str_data_store.bucket_regional_domain_name
}

# Main Application RDS Aurora Outputs
output "rds_cluster_id" {
  description = "Main RDS cluster identifier"
  value       = aws_rds_cluster.main.cluster_identifier
}

output "rds_cluster_endpoint" {
  description = "Main RDS cluster endpoint"
  value       = aws_rds_cluster.main.endpoint
}

output "rds_cluster_reader_endpoint" {
  description = "Main RDS cluster reader endpoint"
  value       = aws_rds_cluster.main.reader_endpoint
}

output "rds_cluster_port" {
  description = "Main RDS cluster port"
  value       = aws_rds_cluster.main.port
}

output "rds_cluster_database_name" {
  description = "Main RDS cluster database name"
  value       = aws_rds_cluster.main.database_name
}

output "rds_cluster_master_username" {
  description = "Main RDS cluster master username"
  value       = aws_rds_cluster.main.master_username
  sensitive   = true
}

output "rds_cluster_arn" {
  description = "Main RDS cluster ARN"
  value       = aws_rds_cluster.main.arn
}

output "rds_instance_endpoints" {
  description = "Main RDS instance endpoints"
  value       = aws_rds_cluster_instance.main[*].endpoint
}

output "rds_instance_identifiers" {
  description = "Main RDS instance identifiers"
  value       = aws_rds_cluster_instance.main[*].identifier
}

# Bedrock Knowledge Base RDS Aurora Outputs
output "bedrock_rds_cluster_id" {
  description = "Bedrock RDS cluster identifier"
  value       = aws_rds_cluster.bedrock.cluster_identifier
}

output "bedrock_rds_cluster_endpoint" {
  description = "Bedrock RDS cluster endpoint"
  value       = aws_rds_cluster.bedrock.endpoint
}

output "bedrock_rds_cluster_reader_endpoint" {
  description = "Bedrock RDS cluster reader endpoint"
  value       = aws_rds_cluster.bedrock.reader_endpoint
}

output "bedrock_rds_cluster_port" {
  description = "Bedrock RDS cluster port"
  value       = aws_rds_cluster.bedrock.port
}

output "bedrock_rds_cluster_arn" {
  description = "Bedrock RDS cluster ARN"
  value       = aws_rds_cluster.bedrock.arn
}

output "bedrock_rds_instance_endpoints" {
  description = "Bedrock RDS instance endpoints"
  value       = aws_rds_cluster_instance.bedrock[*].endpoint
}

output "bedrock_rds_instance_identifiers" {
  description = "Bedrock RDS instance identifiers"
  value       = aws_rds_cluster_instance.bedrock[*].identifier
}

# Secrets Manager Outputs
output "db_password_secret_arn" {
  description = "ARN of the database password secret in AWS Secrets Manager"
  value       = aws_secretsmanager_secret.db_password.arn
}

output "db_password_secret_name" {
  description = "Name of the database password secret in AWS Secrets Manager"
  value       = aws_secretsmanager_secret.db_password.name
}

# Security Group Outputs
output "rds_security_group_id" {
  description = "ID of the RDS security group"
  value       = aws_security_group.rds.id
}

# NAT Gateway Outputs
output "nat_gateway_ids" {
  description = "IDs of the NAT Gateways"
  value       = aws_nat_gateway.main[*].id
}

output "nat_gateway_public_ips" {
  description = "Public IPs of the NAT Gateways"
  value       = aws_eip.nat[*].public_ip
}


# Bedrock Knowledge Base Outputs
output "bedrock_knowledge_base_id" {
  description = "ID of the Bedrock Knowledge Base"
  value       = aws_bedrockagent_knowledge_base.main.id
}

output "bedrock_knowledge_base_arn" {
  description = "ARN of the Bedrock Knowledge Base"
  value       = aws_bedrockagent_knowledge_base.main.arn
}

output "bedrock_data_source_id" {
  description = "ID of the Bedrock Knowledge Base data source"
  value       = aws_bedrockagent_data_source.s3_data_source.data_source_id
}

output "bedrock_kb_secret_arn" {
  description = "ARN of the Bedrock Knowledge Base secret"
  value       = aws_secretsmanager_secret.bedrock_kb_secret.arn
}

output "bedrock_kb_role_arn" {
  description = "ARN of the Bedrock Knowledge Base IAM role"
  value       = aws_iam_role.bedrock_kb_role.arn
}

output "bedrock_model_access_status" {
  description = "Instructions for enabling Bedrock model access"
  value       = <<-EOT
📋 Bedrock Model Access Instructions:

If you get a "403" error when syncing the Knowledge Base:

1. 🌐 Go to AWS Bedrock Console:
   https://${var.aws_region}.console.aws.amazon.com/bedrock/home?region=${var.aws_region}#/modelaccess

2. 🔓 Enable model access:
   - Click "Model access" in left navigation
   - Find "Amazon Titan Text Embeddings V2"
   - Click "Request model access" or "Enable"
   - Wait for approval (usually instant)

3. 🔄 Re-sync your Knowledge Base data source

Model ARN: arn:aws:bedrock:${var.aws_region}::foundation-model/amazon.titan-embed-text-v2:0
EOT
}

# Cognito Outputs
output "cognito_user_pool_id" {
  description = "ID of the Cognito User Pool"
  value       = aws_cognito_user_pool.main.id
}

output "cognito_user_pool_arn" {
  description = "ARN of the Cognito User Pool"
  value       = aws_cognito_user_pool.main.arn
}

output "cognito_user_pool_client_id" {
  description = "ID of the Cognito User Pool Client"
  value       = aws_cognito_user_pool_client.main.id
}

output "cognito_user_pool_domain" {
  description = "Domain name of the Cognito User Pool"
  value       = aws_cognito_user_pool_domain.main.domain
}

output "cognito_hosted_ui_url" {
  description = "URL for Cognito Hosted UI"
  value       = "https://${aws_cognito_user_pool_domain.main.domain}.auth.${var.aws_region}.amazoncognito.com"
}

# Lambda Outputs
output "lambda_function_name" {
  description = "Name of the Lambda function"
  value       = aws_lambda_function.post_confirmation.function_name
}

output "lambda_function_arn" {
  description = "ARN of the Lambda function"
  value       = aws_lambda_function.post_confirmation.arn
} 