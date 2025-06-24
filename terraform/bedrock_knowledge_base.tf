# Bedrock Knowledge Base Configuration
# Currently commented out for simplified testing
# 
# This file contains configuration for:
# - AWS Bedrock Knowledge Base
# - S3 data source integration
# - RDS PostgreSQL vector database
# - IAM roles and policies for Bedrock service
# - Database setup automation
#
# To enable: uncomment resources and ensure dependencies are active:
# - aws_s3_bucket.str_data_store (in s3.tf)
# - aws_rds_cluster.bedrock (in rds.tf) 
# - random_password.bedrock_db_password (in rds.tf) 