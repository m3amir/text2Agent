# AWS Configuration
aws_region  = "us-west-2"
aws_profile = "m3"

# Environment Configuration
environment  = "dev"
project_name = "text2agent"

# S3 Configuration
s3_bucket_name_prefix = "text2agent"
s3_versioning_enabled = true

# RDS Aurora Configuration
db_cluster_identifier   = "text2agent-aurora-cluster"
db_name                 = "text2agent"
db_master_username      = "postgres"
db_instance_class       = "db.r6g.large"
db_instance_count       = 1
backup_retention_period = 7
backup_window           = "03:00-04:00"
maintenance_window      = "sun:04:00-sun:05:00"

# Network Configuration
vpc_cidr             = "10.0.0.0/16"
private_subnet_cidrs = ["10.0.1.0/24", "10.0.2.0/24"]
public_subnet_cidrs  = ["10.0.101.0/24", "10.0.102.0/24"]
allowed_cidr_blocks  = ["10.0.0.0/16"]

# Bedrock Knowledge Base Semantic Chunking Configuration
chunking_strategy                        = "SEMANTIC"
semantic_breakpoint_percentile_threshold = 95
semantic_buffer_size                     = 1
semantic_max_tokens                      = 300

 