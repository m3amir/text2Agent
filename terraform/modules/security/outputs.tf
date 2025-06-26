# Security outputs - currently commented out
# Will be enabled when IAM and Secrets Manager resources are uncommented 

# ==============================================================================
# SECURITY MODULE OUTPUTS
# ==============================================================================

output "app_secrets_arn" {
  description = "ARN of the application secrets"
  value       = aws_secretsmanager_secret.app_secrets.arn
}

output "app_secrets_name" {
  description = "Name of the application secrets"
  value       = aws_secretsmanager_secret.app_secrets.name
}

output "enhanced_monitoring_role_arn" {
  description = "ARN of the enhanced monitoring IAM role"
  value       = aws_iam_role.enhanced_monitoring.arn
}

output "enhanced_monitoring_role_name" {
  description = "Name of the enhanced monitoring IAM role"
  value       = aws_iam_role.enhanced_monitoring.name
} 