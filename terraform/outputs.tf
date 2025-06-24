# output "vpc_id" {
#   value = aws_vpc.main.id
# }
#
# output "vpc_cidr_block" {
#   value = aws_vpc.main.cidr_block
# }
#
# output "public_subnet_ids" {
#   value = aws_subnet.public[*].id
# }
#
# output "private_subnet_ids" {
#   value = aws_subnet.private[*].id
# }

# STR Data Store S3 Bucket Outputs
# output "str_data_store_bucket_id" {
#   value = aws_s3_bucket.str_data_store.id
# }
#
# output "str_data_store_bucket_arn" {
#   value = aws_s3_bucket.str_data_store.arn
# }
#
# output "str_data_store_bucket_domain_name" {
#   value = aws_s3_bucket.str_data_store.bucket_domain_name
# }
#
# output "str_data_store_bucket_regional_domain_name" {
#   value = aws_s3_bucket.str_data_store.bucket_regional_domain_name
# }

# Main Application RDS Aurora Outputs
# output "rds_cluster_id" {
#   value = aws_rds_cluster.main.cluster_identifier
# }
#
# output "rds_cluster_endpoint" {
#   value = aws_rds_cluster.main.endpoint
# }
#
# output "rds_cluster_reader_endpoint" {
#   value = aws_rds_cluster.main.reader_endpoint
# }
#
# output "rds_cluster_port" {
#   value = aws_rds_cluster.main.port
# }
#
# output "rds_cluster_database_name" {
#   value = aws_rds_cluster.main.database_name
# }
#
# output "rds_cluster_master_username" {
#   value = aws_rds_cluster.main.master_username
#   sensitive = true
# }
#
# output "rds_cluster_arn" {
#   value = aws_rds_cluster.main.arn
# }
#
# output "rds_instance_endpoints" {
#   value = aws_rds_cluster_instance.main[*].endpoint
# }
#
# output "rds_instance_identifiers" {
#   value = aws_rds_cluster_instance.main[*].identifier
# }

# Bedrock Knowledge Base RDS Aurora Outputs
# output "bedrock_rds_cluster_id" {
#   value = aws_rds_cluster.bedrock.cluster_identifier
# }
#
# output "bedrock_rds_cluster_endpoint" {
#   value = aws_rds_cluster.bedrock.endpoint
# }
#
# output "bedrock_rds_cluster_reader_endpoint" {
#   value = aws_rds_cluster.bedrock.reader_endpoint
# }
#
# output "bedrock_rds_cluster_port" {
#   value = aws_rds_cluster.bedrock.port
# }
#
# output "bedrock_rds_cluster_arn" {
#   value = aws_rds_cluster.bedrock.arn
# }
#
# output "bedrock_rds_instance_endpoints" {
#   value = aws_rds_cluster_instance.bedrock[*].endpoint
# }
#
# output "bedrock_rds_instance_identifiers" {
# output "str_data_store_bucket_domain_name" {
#   value = aws_s3_bucket.str_data_store.bucket_domain_name
# }
#
# output "str_data_store_bucket_regional_domain_name" {
#   value = aws_s3_bucket.str_data_store.bucket_regional_domain_name
# }

# output "rds_instance_identifiers" {
#   value = aws_rds_cluster_instance.main[*].identifier
# }

# output "bedrock_knowledge_base_id" {
#   value = try(aws_bedrockagent_knowledge_base.main.id, "not-created")
# }
#
# output "bedrock_knowledge_base_arn" {
#   value = try(aws_bedrockagent_knowledge_base.main.arn, "not-created")
# }
#
# output "lambda_function_name" {
#   value = aws_lambda_function.post_confirmation.function_name
# }

# output "lambda_function_arn" {
#   value = aws_lambda_function.post_confirmation.arn
# }