# ==============================================================================
# TEXT2AGENT INFRASTRUCTURE - MODULAR DEPLOYMENT
# Complete infrastructure using modular approach
# ==============================================================================

# ==============================================================================
# PROVIDERS AND BACKEND
# ==============================================================================

terraform {
  required_version = ">= 1.0"

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

  backend "s3" {
    bucket = "text2agent-terraform-state-eu-west-2"
    key    = "text2agent/production/terraform.tfstate"
    region = "eu-west-2"
  }
}

provider "aws" {
  region                   = var.aws_region
  profile                  = var.aws_profile != "" ? var.aws_profile : null
  shared_credentials_files = var.aws_profile != "" ? ["~/.aws/credentials"] : null

  default_tags {
    tags = {
      Project     = var.project_name
      Environment = var.environment
      ManagedBy   = "Terraform"
    }
  }
}

# ==============================================================================
# LOCAL VALUES
# ==============================================================================

locals {
  common_tags = {
    Project     = var.project_name
    Environment = var.environment
    ManagedBy   = "Terraform"
  }
}

# ==============================================================================
# NETWORKING MODULE
# VPC, Subnets, Route Tables, etc.
# ==============================================================================

module "networking" {
  source = "./modules/networking"

  project_name = var.project_name
  environment  = var.environment

  vpc_cidr             = "10.0.0.0/16"
  private_subnet_cidrs = ["10.0.1.0/24", "10.0.2.0/24"]
  public_subnet_cidrs  = ["10.0.101.0/24", "10.0.102.0/24"]
}

# ==============================================================================
# SECURITY MODULE
# IAM roles, policies, secrets management
# ==============================================================================

module "security" {
  source = "./modules/security"

  project_name = var.project_name
  environment  = var.environment
  aws_region   = var.aws_region
}

# ==============================================================================
# STORAGE MODULE
# S3 buckets and related configurations
# ==============================================================================

module "storage" {
  source = "./modules/storage"

  project_name = var.project_name
  environment  = var.environment
  aws_region   = var.aws_region
}

# ==============================================================================
# DATABASE MODULE
# Aurora PostgreSQL cluster with pgvector extension
# ==============================================================================

module "database" {
  source = "./modules/database"

  project_name = var.project_name
  environment  = var.environment
  aws_region   = var.aws_region

  vpc_id             = module.networking.vpc_id
  vpc_cidr_block     = module.networking.vpc_cidr_block
  private_subnet_ids = module.networking.private_subnet_ids
  public_subnet_ids  = module.networking.public_subnet_ids

  # Optional: Override the default cluster identifier
  # cluster_identifier = "your-custom-cluster-name"
}

# ==============================================================================
# AI MODULE
# Bedrock Knowledge Base with Aurora PostgreSQL vector store
# ==============================================================================

module "ai" {
  source = "./modules/ai"

  project_name = var.project_name
  environment  = var.environment
  aws_region   = var.aws_region
  tags         = local.common_tags

  # S3 Configuration
  s3_bucket_arn = module.storage.s3_bucket_arn

  # Database Configuration
  db_cluster_arn            = module.database.cluster_arn
  db_master_user_secret_arn = module.database.secret_arn
  db_name                   = module.database.database_name
  db_schema_dependency      = module.database.bedrock_readiness_id
}

# ==============================================================================
# AUTH MODULE
# Cognito User Pool and Lambda function for post-confirmation
# ==============================================================================

module "auth" {
  source = "./modules/auth"

  project_name = var.project_name
  environment  = var.environment
  aws_region   = var.aws_region

  # Network Configuration
  vpc_id             = module.networking.vpc_id
  private_subnet_ids = module.networking.private_subnet_ids

  # Database Configuration
  database_host         = module.database.cluster_endpoint
  rds_security_group_id = module.database.rds_security_group_id

  # Lambda Configuration
  lambda_zip_path           = "./post_confirmation.zip"
  psycopg2_layer_zip_path   = "./psycopg2-layer.zip"
}

 