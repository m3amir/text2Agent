variable "aws_region" {
  description = "AWS region for resources"
  type        = string
  default     = "us-west-2"
}

variable "aws_profile" {
  description = "AWS profile to use (leave empty for CI/CD environments)"
  type        = string
  default     = ""
}

variable "environment" {
  description = "Environment name (e.g., dev, staging, prod)"
  type        = string
  default     = "dev"
}

variable "project_name" {
  description = "Name of the project"
  type        = string
  default     = "text2agent"
}

# S3 Variables
variable "s3_bucket_name_prefix" {
  description = "Prefix for S3 bucket name"
  type        = string
  default     = "text2agent"
}

variable "s3_versioning_enabled" {
  description = "Enable versioning for S3 bucket"
  type        = bool
  default     = true
}

# RDS Aurora Variables
variable "db_cluster_identifier" {
  description = "Identifier for the Aurora cluster"
  type        = string
  default     = "text2agent-aurora-cluster"
}

variable "db_name" {
  description = "Name of the database"
  type        = string
  default     = "text2agent"
}

variable "db_master_username" {
  description = "Master username for the database"
  type        = string
  default     = "postgres"
}

variable "db_instance_class" {
  description = "Instance class for Aurora instances"
  type        = string
  default     = "db.r6g.large"
}

variable "db_instance_count" {
  description = "Number of instances in the Aurora cluster"
  type        = number
  default     = 1
}

variable "backup_retention_period" {
  description = "Backup retention period in days"
  type        = number
  default     = 7
}

variable "backup_window" {
  description = "Preferred backup window"
  type        = string
  default     = "03:00-04:00"
}

variable "maintenance_window" {
  description = "Preferred maintenance window"
  type        = string
  default     = "sun:04:00-sun:05:00"
}

variable "vpc_cidr" {
  description = "CIDR block for VPC"
  type        = string
  default     = "10.0.0.0/16"
}

variable "private_subnet_cidrs" {
  description = "CIDR blocks for private subnets"
  type        = list(string)
  default     = ["10.0.1.0/24", "10.0.2.0/24"]
}

variable "public_subnet_cidrs" {
  description = "CIDR blocks for public subnets"
  type        = list(string)
  default     = ["10.0.101.0/24", "10.0.102.0/24"]
}

variable "allowed_cidr_blocks" {
  description = "CIDR blocks allowed to access the database"
  type        = list(string)
  default     = ["10.0.0.0/16"]
}



# Cognito Variables
variable "cognito_user_pool_id" {
  description = "Cognito User Pool ID for Lambda post-confirmation trigger"
  type        = string
  default     = ""
}

# Bedrock Knowledge Base Semantic Chunking Variables
variable "chunking_strategy" {
  description = "Chunking strategy for Bedrock Knowledge Base (FIXED_SIZE, NONE, HIERARCHICAL, SEMANTIC)"
  type        = string
  default     = "SEMANTIC"

  validation {
    condition     = contains(["FIXED_SIZE", "NONE", "HIERARCHICAL", "SEMANTIC"], var.chunking_strategy)
    error_message = "Chunking strategy must be one of: FIXED_SIZE, NONE, HIERARCHICAL, SEMANTIC."
  }
}

variable "semantic_breakpoint_percentile_threshold" {
  description = "Percentile threshold for semantic chunking breakpoints (0-100)"
  type        = number
  default     = 95

  validation {
    condition     = var.semantic_breakpoint_percentile_threshold >= 50 && var.semantic_breakpoint_percentile_threshold <= 99
    error_message = "Breakpoint percentile threshold must be between 50 and 99."
  }
}

variable "semantic_buffer_size" {
  description = "Buffer size for semantic chunking"
  type        = number
  default     = 1

  validation {
    condition     = var.semantic_buffer_size >= 0 && var.semantic_buffer_size <= 2
    error_message = "Buffer size must be between 0 and 2."
  }
}

variable "semantic_max_tokens" {
  description = "Maximum tokens per chunk for semantic chunking"
  type        = number
  default     = 300

  validation {
    condition     = var.semantic_max_tokens >= 20 && var.semantic_max_tokens <= 8192
    error_message = "Max tokens must be between 20 and 8192."
  }
} 