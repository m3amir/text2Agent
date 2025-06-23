# Text2Agent AWS Infrastructure

This Terraform configuration deploys a complete AWS infrastructure for the Text2Agent project, including a serverless architecture with Aurora PostgreSQL, Bedrock Knowledge Base, Cognito authentication, Lambda functions, and S3 storage.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                         VPC (10.0.0.0/16)                  │
├─────────────────────────┬───────────────────────────────────┤
│    Public Subnets       │        Private Subnets            │
│                         │                                   │
│  ┌─────────────────┐   │  ┌─────────────────────────────┐  │
│  │  NAT Gateway    │   │  │     RDS Aurora Cluster      │  │
│  │                 │   │  │   (PostgreSQL 15.4)         │  │
│  └─────────────────┘   │  │    with Data API            │  │
│                         │  │                             │  │
│  ┌─────────────────┐   │  │  ┌─────────┐ ┌─────────┐   │  │
│  │ Internet Gateway│   │  │  │Instance1│ │Instance2│   │  │
│  └─────────────────┘   │  │  └─────────┘ └─────────┘   │  │
│                         │  └─────────────────────────────┘  │
└─────────────────────────┴───────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                  Amazon Bedrock Knowledge Base             │
│          (Vector Search with Aurora PostgreSQL)            │
│                                                             │
│  ┌─────────────────┐   ┌─────────────────────────────┐    │
│  │   S3 Data       │   │    Aurora PostgreSQL        │    │
│  │   Source        │──▶│   (pgvector extension)      │    │
│  └─────────────────┘   └─────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                     Authentication & APIs                  │
│                                                             │
│  ┌─────────────────┐   ┌─────────────────────────────┐    │
│  │   Cognito User  │   │      Lambda Functions       │    │
│  │      Pool       │   │   (Post-confirmation)       │    │
│  └─────────────────┘   └─────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
```

## File Structure & Purpose

### Core Terraform Files

| File | Purpose | Description |
|------|---------|-------------|
| `terraform.tf` | Provider Configuration | Defines required providers (AWS, random, local) and AWS provider settings including the "m3" profile |
| `variables.tf` | Variable Definitions | Declares all input variables with types, defaults, and descriptions |
| `terraform.tfvars` | Variable Values | Sets actual values for variables (customize this for your environment) |
| `outputs.tf` | Output Values | Defines output values that are displayed after deployment |
| `main.tf` | Main Configuration | Contains the random ID generator and primary resource references |

### Infrastructure Modules

| File | Purpose | Description |
|------|---------|-------------|
| `vpc.tf` | Networking | Creates VPC, subnets, internet gateway, NAT gateways, and route tables |
| `rds.tf` | Database | Deploys Aurora PostgreSQL cluster with serverless v2 scaling and Data API |
| `s3.tf` | Object Storage | Creates encrypted S3 bucket with versioning for document storage |
| `secrets.tf` | Secrets Management | Manages database credentials in AWS Secrets Manager |
| `iam.tf` | IAM Roles | Creates IAM roles and policies for various services |
| `cognito.tf` | Authentication | Sets up Cognito User Pool and User Pool Client for authentication |
| `lambda.tf` | Serverless Functions | Deploys Lambda functions for user management and triggers |
| `bedrock_knowledge_base.tf` | AI/ML Services | Configures Bedrock Knowledge Base with Aurora PostgreSQL backend |

### Support Files

| File | Purpose | Description |
|------|---------|-------------|
| `setup_bedrock_database.sql` | Database Setup | SQL commands to initialize the database for Bedrock Knowledge Base |
| `package_lambda.sh` | Build Script | Shell script to package Lambda functions for deployment |
| `lambda_functions/` | Function Code | Directory containing Lambda function source code |
| `.terraform.lock.hcl` | Dependency Lock | Locks provider versions for consistent deployments |
| `terraform.tfstate*` | State Files | Tracks the current state of deployed infrastructure |

## Prerequisites

1. **AWS CLI** configured with "m3" profile
   ```bash
   aws configure --profile m3
   # Enter your access key, secret key, region (us-west-2), and output format (json)
   ```

2. **Terraform** >= 1.0 installed
   ```bash
   # macOS
   brew install terraform
   
   # Or download from https://www.terraform.io/downloads
   ```

3. **Required AWS IAM Permissions**:
   - VPC management (EC2)
   - RDS Aurora management
   - S3 bucket management
   - Secrets Manager access
   - Cognito management
   - Lambda management
   - Bedrock access
   - IAM role/policy management

## Quick Start Guide

### 1. Initial Setup

```bash
# Navigate to terraform directory
cd terraform

# Activate Python virtual environment (if using one)
source ../venv/bin/activate

# Copy example variables (if it exists, or use existing terraform.tfvars)
# The terraform.tfvars file contains your environment-specific settings
cat terraform.tfvars
```

### 2. Initialize Terraform

```bash
# Download providers and modules
terraform init

# If you need to upgrade providers (required for null provider)
terraform init -upgrade
```

**What this does**: Downloads the AWS, random, local, and null providers specified in `terraform.tf` and initializes the backend for state management.

### 3. Plan Deployment

```bash
# See what will be created/changed/destroyed
terraform plan

# Save plan to file for review
terraform plan -out=tfplan
```

**What this does**: Compares your configuration files against the current state and shows exactly what Terraform will do without making any changes.

### 4. Deploy Infrastructure (Current Process)

```bash
# Apply all changes with automated Bedrock setup
terraform apply

# Or apply from saved plan
terraform apply tfplan

# Auto-approve (skip confirmation prompt) - Use with caution
terraform apply -auto-approve
```

**What this does**: Creates all the AWS resources in the following order with automated fixes:

#### Phase 1: Core Infrastructure (2-3 minutes)
1. **VPC & Networking**: Creates VPC, subnets, internet gateway, NAT gateways
2. **Security Groups**: Sets up RDS and Lambda security groups
3. **IAM Roles**: Creates roles for RDS monitoring, Lambda, and Bedrock services
4. **S3 Buckets**: Creates main bucket and structured data store with encryption

#### Phase 2: Database Setup (8-12 minutes)
5. **Aurora PostgreSQL Cluster**: Creates serverless Aurora cluster with Data API enabled
6. **Aurora Instances**: Provisions database instances (this takes the longest)
7. **Secrets Manager**: Stores database credentials securely
8. **Database Validation**: Waits for cluster to be fully available

#### Phase 3: Automated Bedrock Database Setup (1-2 minutes)
9. **Database Schema Creation**: Automatically runs via `null_resource.bedrock_db_setup`:
   ```sql
   -- Creates vector extension for embeddings
   CREATE EXTENSION IF NOT EXISTS vector;
   
   -- Creates dedicated schema for Bedrock
   CREATE SCHEMA IF NOT EXISTS bedrock_integration;
   
   -- Creates optimized table for vector storage
   CREATE TABLE bedrock_integration.bedrock_kb (
     id uuid PRIMARY KEY,
     embedding vector(1024),
     chunks text,
     metadata json
   );
   
   -- Creates indexes for optimal performance
   CREATE INDEX ON bedrock_integration.bedrock_kb USING hnsw (embedding vector_cosine_ops);
   ```

#### Phase 4: Authentication & Serverless (2-3 minutes)
10. **Cognito User Pool**: Sets up authentication system
11. **Lambda Functions**: Deploys post-confirmation triggers
12. **Lambda Permissions**: Configures Cognito-Lambda integration

#### Phase 5: Bedrock Knowledge Base (3-5 minutes)
13. **Bedrock Knowledge Base**: Creates the knowledge base with Aurora PostgreSQL backend
14. **S3 Data Source**: Links the S3 bucket as a data source
15. **Data Source Sync**: Configures automatic document ingestion

### 5. Automated Database Setup (Now Included)

**✅ No Manual Steps Required**: The database setup is now fully automated through Terraform!

The `null_resource.bedrock_db_setup` automatically:
- Uses the correct AWS profile (`m3`) and region (`us-west-2`)
- Waits for the RDS cluster to be fully available
- Creates the `vector` extension for embeddings
- Sets up the `bedrock_integration` schema
- Creates the optimized vector table with proper indexes
- Uses the same credentials as the Bedrock Knowledge Base

**Previous Manual Process** (now automated):
```bash
# This is no longer needed - it's automated!
aws rds-data execute-statement \
  --profile m3 \
  --region us-west-2 \
  --resource-arn "$(terraform output -raw aurora_cluster_arn)" \
  --database "postgres" \
  --secret-arn "$(terraform output -raw db_password_secret_arn)" \
  --sql "$(cat setup_bedrock_database.sql)"
```

### 6. View Deployment Results

```bash
# Show all outputs after deployment completes
terraform output

# Key outputs to verify successful deployment:
terraform output bedrock_knowledge_base_id
terraform output aurora_cluster_endpoint  
terraform output s3_bucket_id
terraform output cognito_user_pool_id
```

## Current Deployment Status

The infrastructure deployment includes several **critical fixes** for Bedrock Knowledge Base integration:

### ✅ Issues Resolved

1. **Region Mismatch**: All AWS CLI commands now use explicit `--region us-west-2`
2. **Profile Configuration**: All commands use the correct `--profile m3` 
3. **Authentication**: Bedrock now uses the main `postgres` user instead of a separate `bedrock_user`
4. **Password Synchronization**: Both RDS and Bedrock use the same credential source
5. **Timing Issues**: Added proper dependency chains and wait conditions
6. **Automated Setup**: Database schema creation is fully automated via Terraform

### 🔄 Deployment Process

The current `terraform apply` will:
1. Create a clean infrastructure from scratch
2. Automatically configure the database for Bedrock
3. Establish proper authentication between services
4. Set up the complete vector search pipeline

**Expected Total Time**: 15-20 minutes

**No Manual Intervention Required**: Everything is automated!

## Monitoring Current Deployment

### Real-time Progress Tracking

```bash
# Check if Terraform is still running
ps aux | grep terraform

# Monitor AWS resources being created
watch -n 30 'aws ec2 describe-vpcs --profile m3 --region us-west-2 --query "Vpcs[?Tags[?Key=='\''Project'\'' && Value=='\''text2agent'\'']].VpcId" --output table'

# Check RDS cluster status
aws rds describe-db-clusters --profile m3 --region us-west-2 --query "DBClusters[?DBClusterIdentifier=='text2agent-aurora-cluster'].Status" --output text

# Monitor Bedrock Knowledge Base creation
aws bedrock-agent list-knowledge-bases --profile m3 --region us-west-2 --query "knowledgeBaseSummaries[?name=='text2agent-dev-knowledge-base']" --output table
```

### Deployment Phase Indicators

**Phase 1 Complete** - When you see:
```
aws_vpc.main: Creation complete
aws_subnet.public[0]: Creation complete
aws_internet_gateway.main: Creation complete
```

**Phase 2 Complete** - When you see:
```
aws_rds_cluster.main: Creation complete
aws_rds_cluster_instance.main[0]: Creation complete
```

**Phase 3 Complete** - When you see:
```
null_resource.bedrock_db_setup: Creation complete
local_file.bedrock_db_setup_script: Creation complete
```

**Phase 4 Complete** - When you see:
```
aws_cognito_user_pool.main: Creation complete
aws_lambda_function.post_confirmation: Creation complete
```

**Phase 5 Complete** - When you see:
```
aws_bedrockagent_knowledge_base.main: Creation complete
aws_bedrockagent_data_source.s3_data_source: Creation complete
```

### If Issues Occur During Deployment

#### Database Setup Failures
If `null_resource.bedrock_db_setup` fails:
```bash
# Check the specific error in Terraform output
# Common issues and solutions:

# 1. AWS CLI not found or wrong profile
aws sts get-caller-identity --profile m3

# 2. RDS cluster not ready - just retry
terraform apply -target=null_resource.bedrock_db_setup

# 3. Permission issues - verify IAM
aws rds describe-db-clusters --profile m3 --region us-west-2
```

#### Bedrock Knowledge Base Failures
If the Knowledge Base creation fails:
```bash
# Check if the database table was created
aws rds-data execute-statement \
  --profile m3 \
  --region us-west-2 \
  --resource-arn "$(terraform output -raw aurora_cluster_arn)" \
  --database "postgres" \
  --secret-arn "$(terraform output -raw db_password_secret_arn)" \
  --sql "SELECT table_name FROM information_schema.tables WHERE table_schema = 'bedrock_integration';"

# Retry Knowledge Base creation specifically
terraform apply -target=aws_bedrockagent_knowledge_base.main
```

#### Network/Timeout Issues
```bash
# Check VPC and networking
aws ec2 describe-vpcs --profile m3 --region us-west-2 --filters "Name=tag:Project,Values=text2agent"

# Verify NAT gateways are ready
aws ec2 describe-nat-gateways --profile m3 --region us-west-2 --filter "Name=tag:Project,Values=text2agent"
```

### Success Indicators

**✅ Deployment Successful** when you see:
```
Apply complete! Resources: 63 added, 0 changed, 0 destroyed.

Outputs:
bedrock_knowledge_base_id = "XXXXXXXXX"
aurora_cluster_endpoint = "text2agent-aurora-cluster.cluster-xxxxx.us-west-2.rds.amazonaws.com"
s3_bucket_id = "text2agent-dev-xxxxxxxx"
```

**Test the Complete System**:
```bash
# 1. Test database connection
aws rds-data execute-statement \
  --profile m3 \
  --region us-west-2 \
  --resource-arn "$(terraform output -raw aurora_cluster_arn)" \
  --database "postgres" \
  --secret-arn "$(terraform output -raw db_password_secret_arn)" \
  --sql "SELECT version();"

# 2. Upload a test document
aws s3 cp README.md s3://$(terraform output -raw s3_bucket_id)/test-doc.md --profile m3

# 3. Check Knowledge Base status
aws bedrock-agent get-knowledge-base \
  --profile m3 \
  --region us-west-2 \
  --knowledge-base-id "$(terraform output -raw bedrock_knowledge_base_id)"
```

## Essential Terraform Commands

### State Management

```bash
# List all resources in state
terraform state list

# Show details of specific resource
terraform state show aws_rds_cluster.main

# Remove resource from state (without destroying)
terraform state rm aws_s3_bucket.main

# Import existing AWS resource into state
terraform import aws_s3_bucket.main my-existing-bucket-name
```

### Resource Targeting

```bash
# Plan changes for specific resources only
terraform plan -target=aws_rds_cluster.main

# Apply changes to specific resources only
terraform apply -target=aws_s3_bucket.main -target=aws_rds_cluster.main

# Destroy specific resources only
terraform destroy -target=aws_bedrockagent_knowledge_base.main
```

### Validation & Formatting

```bash
# Validate configuration syntax
terraform validate

# Format all .tf files consistently
terraform fmt -recursive

# Check for potential issues
terraform plan -detailed-exitcode
```

### Working with Variables

```bash
# Override variables from command line
terraform apply -var="environment=production" -var="db_instance_count=3"

# Use different variables file
terraform apply -var-file="production.tfvars"

# Set variables via environment (prefix with TF_VAR_)
export TF_VAR_environment=staging
terraform apply
```

## Configuration Guide

### Key Variables to Customize

Edit `terraform.tfvars` to customize your deployment:

```hcl
# Basic Configuration
aws_region = "us-west-2"
environment = "dev"  # or "staging", "production"
project_name = "text2agent"

# Database Configuration
db_instance_count = 2  # 1 for dev, 2+ for production
db_instance_class = "db.r6g.large"  # or db.t4g.medium for dev

# S3 Configuration
s3_versioning_enabled = true
```

### Environment-Specific Configurations

For different environments, consider:

**Development (`dev`)**:
```hcl
environment = "dev"
db_instance_count = 1
db_instance_class = "db.t4g.medium"
backup_retention_period = 1
```

**Production (`prod`)**:
```hcl
environment = "prod"
db_instance_count = 3
db_instance_class = "db.r6g.xlarge"
backup_retention_period = 30
```

## Using the Bedrock Knowledge Base

### 1. Upload Documents

```bash
# Get bucket name from Terraform output
BUCKET_NAME=$(terraform output -raw s3_bucket_id)

# Upload documents (they'll be auto-ingested)
aws s3 cp ./document.pdf s3://$BUCKET_NAME/
aws s3 cp ./text-file.txt s3://$BUCKET_NAME/
aws s3 sync ./documents/ s3://$BUCKET_NAME/documents/
```

### 2. Query the Knowledge Base

```python
import boto3

# Initialize Bedrock Agent Runtime client
bedrock = boto3.client('bedrock-agent-runtime', region_name='us-west-2')

# Query the knowledge base
response = bedrock.retrieve(
    knowledgeBaseId='YOUR_KB_ID',  # From terraform output
    retrievalQuery={
        'text': 'What are the main topics in the documents?'
    },
    retrievalConfiguration={
        'vectorSearchConfiguration': {
            'numberOfResults': 5
        }
    }
)

# Process results
for result in response['retrievalResults']:
    print(f"Score: {result['score']}")
    print(f"Content: {result['content']['text']}")
    print("---")
```

### 3. Monitor Ingestion

```bash
# Get knowledge base details
KB_ID=$(terraform output -raw bedrock_knowledge_base_id)
DS_ID=$(terraform output -raw bedrock_data_source_id)

# Check ingestion jobs
aws bedrock-agent list-ingestion-jobs \
  --profile m3 \
  --knowledge-base-id $KB_ID \
  --data-source-id $DS_ID
```

## Database Access

### Using RDS Data API (Recommended)

```bash
# Execute SQL via Data API (no VPN/bastion needed)
aws rds-data execute-statement \
  --profile m3 \
  --resource-arn "$(terraform output -raw aurora_cluster_arn)" \
  --database "postgres" \
  --secret-arn "$(terraform output -raw db_password_secret_arn)" \
  --sql "SELECT version();"
```

### Direct Connection (Requires VPN/Bastion)

```bash
# Get connection details
ENDPOINT=$(terraform output -raw aurora_cluster_endpoint)
USERNAME=$(terraform output -raw aurora_cluster_master_username)

# Get password from Secrets Manager
PASSWORD=$(aws secretsmanager get-secret-value \
  --profile m3 \
  --secret-id "$(terraform output -raw db_password_secret_arn)" \
  --query SecretString --output text | jq -r '.password')

# Connect with psql
psql -h $ENDPOINT -U $USERNAME -d postgres
```

## Troubleshooting

### Common Issues

1. **AWS Profile Issues**
   ```bash
   # Verify profile configuration
   aws sts get-caller-identity --profile m3
   
   # If profile doesn't exist, configure it
   aws configure --profile m3
   ```

2. **Terraform State Lock**
   ```bash
   # If state is locked, force unlock (use carefully)
   terraform force-unlock LOCK_ID
   ```

3. **Resource Already Exists**
   ```bash
   # Import existing resource into state
   terraform import aws_s3_bucket.main existing-bucket-name
   ```

4. **Insufficient Permissions**
   ```bash
   # Check current permissions
   aws sts get-caller-identity --profile m3
   aws iam get-user --profile m3
   ```

### Useful Debugging Commands

```bash
# Enable verbose logging
export TF_LOG=DEBUG
terraform apply

# Show provider configuration
terraform providers

# Validate configuration
terraform validate

# Check for syntax errors
terraform fmt -check -recursive
```

## Cost Optimization

### Development Environment

```hcl
# In terraform.tfvars for dev
environment = "dev"
db_instance_count = 1
db_instance_class = "db.t4g.medium"
backup_retention_period = 1
```

### Monitor Costs

```bash
# Check AWS costs via CLI
aws ce get-cost-and-usage \
  --profile m3 \
  --time-period Start=2024-01-01,End=2024-01-31 \
  --granularity MONTHLY \
  --metrics BlendedCost
```

## Cleanup

### Destroy Everything

```bash
# Destroy all resources (WARNING: This deletes all data)
terraform destroy

# Destroy specific resources only
terraform destroy -target=aws_bedrockagent_knowledge_base.main
```

### Partial Cleanup

```bash
# Remove Bedrock resources only
terraform destroy \
  -target=aws_bedrockagent_knowledge_base.main \
  -target=aws_bedrockagent_data_source.main \
  -target=aws_iam_role.bedrock_knowledge_base_role \
  -target=aws_iam_role.bedrock_data_source_role
```

## Security Best Practices

1. **Never commit `terraform.tfvars`** with sensitive data
2. **Use AWS Secrets Manager** for all passwords and keys
3. **Enable VPC Flow Logs** for network monitoring
4. **Regular backup verification** for RDS
5. **Least privilege IAM policies** for all roles
6. **Enable CloudTrail** for audit logging

## Support & Maintenance

### Regular Tasks

1. **Update providers** monthly: `terraform init -upgrade`
2. **Review state** for drift: `terraform plan`
3. **Backup state file** before major changes
4. **Monitor AWS costs** and resource usage
5. **Review security groups** and access patterns