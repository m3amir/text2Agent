# ==============================================================================
# SECURITY MODULE
# General security configurations and IAM resources
# ==============================================================================

# Random ID for unique resource naming
resource "random_id" "secret_suffix" {
  byte_length = 4
}

# General application secrets
resource "aws_secretsmanager_secret" "app_secrets" {
  name        = "${var.project_name}-${var.environment}-app-secrets-${random_id.secret_suffix.hex}"
  description = "Application secrets for ${var.project_name} ${var.environment} environment"

  tags = {
    Name        = "${var.project_name}-${var.environment}-app-secrets"
    Environment = var.environment
    Project     = var.project_name
  }
}

# Default application secrets version (can be updated later)
resource "aws_secretsmanager_secret_version" "app_secrets" {
  secret_id = aws_secretsmanager_secret.app_secrets.id
  secret_string = jsonencode({
    environment = var.environment
    region      = var.aws_region
    project     = var.project_name
  })
}