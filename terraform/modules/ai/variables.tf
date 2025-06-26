# ==============================================================================
# AI MODULE VARIABLES
# Variables for Bedrock Knowledge Base with Aurora PostgreSQL vector store
# ==============================================================================

variable "project_name" {
  description = "Name of the project"
  type        = string
}

variable "environment" {
  description = "Environment name (e.g., dev, staging, prod)"
  type        = string
}

variable "aws_region" {
  description = "AWS region"
  type        = string
}

variable "tags" {
  description = "Common tags to apply to all resources"
  type        = map(string)
  default     = {}
}

# S3 Configuration
variable "s3_bucket_arn" {
  description = "ARN of the S3 bucket containing documents for the knowledge base"
  type        = string
}

# Database Configuration
variable "db_cluster_arn" {
  description = "ARN of the Aurora PostgreSQL cluster"
  type        = string
}

variable "db_master_user_secret_arn" {
  description = "ARN of the Secrets Manager secret containing Aurora master user credentials"
  type        = string
}

variable "db_name" {
  description = "Name of the database in Aurora cluster"
  type        = string
  default     = "postgres"
}

variable "db_schema_dependency" {
  description = "Database schema initialization dependency"
  type        = string
  default     = ""
} 