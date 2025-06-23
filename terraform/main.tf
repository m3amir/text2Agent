# Main configuration file - resources have been organized into separate files for better maintainability:
# - vpc.tf: VPC, subnets, gateways, route tables  
# - rds.tf: RDS Aurora cluster and related resources
# - s3.tf: S3 bucket and configuration
  # - iam.tf: IAM roles and policies
  # - secrets.tf: Secrets Manager resources
  # - bedrock_knowledge_base.tf: Bedrock Knowledge Base with Aurora PostgreSQL
  # - lambda.tf: Lambda functions and related resources
# - cognito.tf: Cognito User Pool and authentication
#
# Configuration files:
# - terraform.tf: Provider configuration (using m3 profile)
# - variables.tf: Variable definitions
# - terraform.tfvars: Variable values
# - outputs.tf: Output definitions 