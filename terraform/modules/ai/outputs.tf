# ==============================================================================
# AI MODULE OUTPUTS
# Outputs for Bedrock Knowledge Base resources
# ==============================================================================

output "knowledge_base_id" {
  description = "ID of the Bedrock Knowledge Base"
  value       = aws_bedrockagent_knowledge_base.main.id
}

output "knowledge_base_arn" {
  description = "ARN of the Bedrock Knowledge Base"
  value       = aws_bedrockagent_knowledge_base.main.arn
}

output "data_source_id" {
  description = "ID of the S3 data source"
  value       = aws_bedrockagent_data_source.s3_documents.data_source_id
}

output "bedrock_service_role_arn" {
  description = "ARN of the Bedrock service role"
  value       = aws_iam_role.bedrock_kb.arn
}

output "embedding_model_arn" {
  description = "ARN of the embedding model"
  value       = data.aws_bedrock_foundation_model.embedding.model_arn
} 