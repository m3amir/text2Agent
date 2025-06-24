terraform {
  required_version = ">= 1.0"

  backend "s3" {
    bucket  = "text2agent-terraform-state-eu-west-2"
    key     = "text2agent/production/terraform.tfstate"
    region  = "eu-west-2"
    encrypt = true
  }

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
    null = {
      source  = "hashicorp/null"
      version = "~> 3.0"
    }
  }
}

provider "aws" {
  region                   = var.aws_region
  profile                  = var.aws_profile != "" ? var.aws_profile : null
  shared_credentials_files = var.aws_profile != "" ? ["~/.aws/credentials"] : null

  default_tags {
    tags = {
      Environment = var.environment
      Project     = var.project_name
      ManagedBy   = "Terraform"
    }
  }
} 