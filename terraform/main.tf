# =====================================================
# ROOT MODULE - Calls child modules
# =====================================================

# Storage Module - ACTIVE (S3 buckets)
module "storage" {
  source = "./modules/storage"
  
  project_name = var.project_name
  environment  = var.environment
  aws_region   = var.aws_region
}

# Authentication Module - ACTIVE (Cognito + Lambda)
module "auth" {
  source = "./modules/auth"
  
  project_name    = var.project_name
  environment     = var.environment
  aws_region      = var.aws_region
  lambda_zip_path = "./post_confirmation.zip"
}

# =====================================================
# FUTURE MODULES - Currently disabled
# Uncomment when ready to deploy
# =====================================================

# # Networking Module - VPC, subnets, gateways
# module "networking" {
#   source = "./modules/networking"
#   
#   project_name         = var.project_name
#   environment          = var.environment
#   vpc_cidr             = var.vpc_cidr
#   private_subnet_cidrs = var.private_subnet_cidrs
#   public_subnet_cidrs  = var.public_subnet_cidrs
# }

# # Database Module - RDS Aurora
# module "database" {
#   source = "./modules/database"
#   
#   project_name = var.project_name
#   environment  = var.environment
#   aws_region   = var.aws_region
#   
#   # Depends on networking
#   # vpc_id         = module.networking.vpc_id
#   # subnet_ids     = module.networking.private_subnet_ids
# }

# # Security Module - IAM, Secrets Manager
# module "security" {
#   source = "./modules/security"
#   
#   project_name = var.project_name
#   environment  = var.environment
#   aws_region   = var.aws_region
# }

# # AI Module - Bedrock Knowledge Base
# module "ai" {
#   source = "./modules/ai"
#   
#   project_name = var.project_name
#   environment  = var.environment
#   aws_region   = var.aws_region
#   
#   # Depends on storage and database
#   # s3_bucket_arn = module.storage.s3_bucket_arn
#   # rds_cluster_arn = module.database.rds_cluster_arn
# } 