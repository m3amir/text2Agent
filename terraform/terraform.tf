terraform {
  required_version = ">= 1.0"

  # Remote state configuration for production
  # Uncomment and configure for production environments
  # backend "s3" {
  #   bucket         = "your-terraform-state-bucket"
  #   key            = "text2agent/${var.environment}/terraform.tfstate"
  #   region         = "eu-west-2"
  #   encrypt        = true
  #   dynamodb_table = "terraform-state-lock"
  # }

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.1"
    }
    local = {
      source  = "hashicorp/local"
      version = "~> 2.0"
    }
  }
}

provider "aws" {
  region = var.aws_region

  # Use profile only when specified (for local development)
  profile = var.aws_profile != "" ? var.aws_profile : null

  # Use credentials file only when profile is specified
  shared_credentials_files = var.aws_profile != "" ? ["~/.aws/credentials"] : null

  default_tags {
    tags = {
      Environment = var.environment
      Project     = var.project_name
      ManagedBy   = "Terraform"
    }
  }
} 