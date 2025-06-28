# Text2Agent Infrastructure

This directory contains the complete Terraform infrastructure for the Text2Agent project - a production-ready Bedrock Knowledge Base system with Aurora PostgreSQL vector database, designed for multi-tenant document search and AI-powered applications.

## 🏗️ Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                         Text2Agent Infrastructure                                │
│                        (Account: 994626600571, Region: eu-west-2)              │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  ┌─────────────────┐   ┌──────────────────┐   ┌─────────────────────────────┐  │
│  │   Cognito       │   │   S3 Bucket      │   │   Aurora Cluster            │  │
│  │ User Pool       │   │ str-data-store-  │   │ text2agent-dev-cluster      │  │
│  │ + Lambda Hooks  │   │ bucket           │   │ (PostgreSQL 15.4)           │  │
│  └─────────────────┘   └──────────────────┘   └─────────────────────────────┘  │
│         │                        │                          │                  │
│         │                        │                          │                  │
│         ▼                        ▼                          ▼                  │
│  ┌─────────────────┐   ┌──────────────────┐   ┌─────────────────────────────┐  │
│  │ Lambda Post-    │   │   Bedrock        │   │   Database 1: str_kb        │  │
│  │ Confirmation    │   │ Knowledge Base   │   │   • bedrock_integration     │  │
│  │ (User mgmt)     │   │ ID: Generated    │   │   • HNSW vector index       │  │
│  └─────────────────┘   └──────────────────┘   │                             │  │
│                                                │   Database 2: text2Agent-   │  │
│                                                │   Tenants                   │  │
│                                                │   • tenantmappings          │  │
│                                                │   • users                   │  │
│                                                └─────────────────────────────┘  │
│                                                                                 │
│              ┌─────────────────────────────────────────────────────┐           │
│              │                   VPC Network                       │           │
│              │  ┌─────────────┐              ┌─────────────────┐   │           │
│              │  │ Public      │              │ Private         │   │           │
│              │  │ Subnets     │              │ Subnets         │   │           │
│              │  │ (NAT GW)    │              │ (DB, Lambda)    │   │           │
│              │  │ AZ-a, AZ-b  │              │ AZ-a, AZ-b      │   │           │
│              │  └─────────────┘              └─────────────────┘   │           │
│              └─────────────────────────────────────────────────────┘           │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### Data Flow Architecture
```
Documents (PDF/TXT) → S3 Bucket → Bedrock Knowledge Base → Titan Embeddings 
                                         ↓
Vector Embeddings (1024d) → Aurora PostgreSQL → HNSW Index → Fast Search
                                         ↓
User Queries → Semantic Search → Top-K Results → Application
```

## 📂 Detailed Module Structure

This infrastructure uses a **modular approach** for better organization, reusability, and dependency management:

```
terraform/
├── main.tf              # Root module - orchestrates all child modules
├── variables.tf         # Input variables (project_name, environment, etc.)
├── outputs.tf           # Output values (endpoints, IDs, connection strings)
├── terraform.tfvars     # Variable values (gitignored - local only)
├── backend.tf           # S3 backend configuration for state management
└── modules/
    ├── networking/      # Module 1: VPC Foundation
    │   ├── main.tf      # VPC, subnets (public/private), route tables
    │   ├── variables.tf # CIDR blocks, AZ configuration
    │   └── outputs.tf   # VPC ID, subnet IDs, security group IDs
    │
    ├── security/        # Module 2: IAM & Secrets
    │   ├── main.tf      # IAM roles, policies, Secrets Manager
    │   ├── variables.tf # Role configurations, policy permissions
    │   └── outputs.tf   # Role ARNs, secret ARNs, policy attachments
    │
    ├── storage/         # Module 3: S3 Storage
    │   ├── main.tf      # S3 bucket with versioning, encryption
    │   ├── variables.tf # Bucket naming, lifecycle policies
    │   └── outputs.tf   # Bucket name, bucket ARN
    │
    ├── database/        # Module 4: Aurora PostgreSQL
    │   ├── main.tf      # Aurora cluster, instances, parameter groups
    │   ├── variables.tf # DB configuration, instance types
    │   ├── outputs.tf   # Endpoints, connection details
    │   └── scripts/     # SQL initialization scripts
    │       ├── init_str_kb.sql           # Bedrock database setup
    │       └── init_text2agent_tenants.sql # Tenant management setup
    │
    ├── ai/              # Module 5: Bedrock Knowledge Base
    │   ├── main.tf      # Knowledge Base, Data Source configurations
    │   ├── variables.tf # Model selection, indexing parameters
    │   └── outputs.tf   # Knowledge Base ID, Data Source ID
    │
    └── auth/            # Module 6: Authentication & User Management
        ├── main.tf      # Cognito User Pool, Lambda functions
        ├── variables.tf # Pool configuration, Lambda settings
        ├── outputs.tf   # User Pool ID, Lambda function ARNs
        └── lambda/      # Lambda function source code
            ├── post_confirmation.py      # User registration handler
            └── requirements.txt          # Python dependencies
```

### Module Dependencies
```
networking (VPC, subnets)
    ↓
security (IAM roles, secrets) + storage (S3 bucket)
    ↓
database (Aurora cluster) - depends on: networking, security
    ↓
ai (Bedrock KB) - depends on: database, storage, security
    ↓
auth (Cognito + Lambda) - depends on: database, security
```

**Key Design Principles:**
- **Separation of Concerns**: Each module handles one infrastructure domain
- **Dependency Management**: Modules depend on outputs from prerequisite modules
- **Reusability**: Modules can be reused across environments (dev/staging/prod)
- **State Isolation**: Each module can be planned/applied independently
- **Security First**: IAM roles follow least-privilege principles

## 🔄 How Terraform Works: Infrastructure as Code

### Terraform State Management

Terraform tracks your infrastructure using a **state file** that maps your configuration to real AWS resources:

```
Local Config (*.tf files) ←→ Terraform State ←→ AWS Resources
```

**State File Location:**
- **Local Development**: `.terraform/terraform.tfstate` (temporary)
- **Production**: S3 backend `s3://text2agent-terraform-state-eu-west-2/text2agent/production/terraform.tfstate`

**Why State Matters:**
- **Tracks Resource Ownership**: Knows which AWS resources belong to this Terraform config
- **Enables Updates**: Can modify existing resources instead of recreating them
- **Prevents Drift**: Detects when AWS resources have been changed outside Terraform
- **Dependency Resolution**: Understands the order in which resources must be created/destroyed

### Terraform Operations Explained

#### 1. `terraform plan` - Preview Changes
```bash
terraform plan -var="aws_profile=m3"
```
**What it does:**
- Compares your `.tf` files against current state
- Queries AWS to check actual resource status
- Shows exactly what will be created/modified/destroyed
- **NEVER** makes actual changes - it's completely safe

**Example output:**
```
Plan: 5 to add, 2 to change, 1 to destroy.

+ aws_db_cluster.aurora_cluster
+ aws_s3_bucket.documents
~ aws_iam_role.bedrock_role
  - aws_security_group.old_sg
```

#### 2. `terraform apply` - Make Changes
```bash
terraform apply -var="aws_profile=m3"
```
**What it does:**
- Runs `terraform plan` first
- Asks for confirmation (unless `-auto-approve`)
- Executes the planned changes in correct order
- Updates the state file
- Shows outputs when complete

#### 3. `terraform destroy` - Remove Everything
```bash
terraform destroy -var="aws_profile=m3"
```
**⚠️ DANGER**: This deletes ALL resources managed by this Terraform config!

### Resource Lifecycle: What Gets Created/Updated/Destroyed

#### 🟢 Resources That Update In-Place (No Downtime)
These can be modified without recreating:
- **Tags** on any resource
- **IAM policy** attachments
- **Lambda function** code
- **S3 bucket** policies
- **Cognito User Pool** attributes (most)
- **Aurora cluster** parameter changes

#### 🟡 Resources That Force Replacement (Recreates Resource)
These changes destroy the old resource and create a new one:
- **Aurora cluster identifier** change
- **VPC CIDR block** change
- **Database name** changes
- **S3 bucket name** changes
- **Lambda function name** changes

#### 🔴 Destructive Operations (Data Loss Risk)
These operations will DELETE data:
- Changing Aurora cluster identifier → **Old database destroyed**
- Changing S3 bucket name → **Old bucket destroyed**
- Running `terraform destroy` → **Everything destroyed**

### When Terraform Deletes Resources

Terraform will delete resources in these scenarios:

#### 1. **Resource Removed from Configuration**
```hcl
# If you remove this block from your .tf files:
# resource "aws_s3_bucket" "example" {
#   bucket = "my-bucket"
# }
```
**Result**: Terraform will delete the S3 bucket on next `apply`

#### 2. **Resource Name Changed**
```hcl
# Old:
resource "aws_db_cluster" "old_name" { ... }
# New:
resource "aws_db_cluster" "new_name" { ... }
```
**Result**: Terraform creates new cluster, then destroys old one

#### 3. **Identifier/Name Properties Changed**
```hcl
resource "aws_db_cluster" "aurora" {
  cluster_identifier = "new-cluster-name"  # Changed from "old-cluster-name"
}
```
**Result**: Forces replacement - destroys old cluster, creates new one

#### 4. **Dependency Changes**
If a parent resource is replaced, dependent resources are also replaced:
```
VPC replacement → Subnets replaced → Aurora cluster replaced
```

### Preventing Accidental Deletions

#### 1. **Use `terraform plan` First**
Always preview changes before applying:
```bash
terraform plan -var="aws_profile=m3" | grep -E "(destroy|replace)"
```

#### 2. **Lifecycle Rules**
```hcl
resource "aws_db_cluster" "aurora" {
  lifecycle {
    prevent_destroy = true  # Prevents accidental deletion
  }
}
```

#### 3. **State Backup**
Before major changes:
```bash
# Backup state file
cp terraform.tfstate terraform.tfstate.backup
```

#### 4. **Import Existing Resources**
If you have existing AWS resources:
```bash
terraform import aws_s3_bucket.existing my-existing-bucket
```

## Deployment Methods

### Method 1: GitHub Actions (Recommended)

**Fully automated deployment through GitHub:**

1. **Push to main branch** → Triggers deployment
2. **GitHub Actions** runs Terraform automatically
3. **No local setup required!**

```bash
# Just push your changes:
git add .
git commit -m "Deploy infrastructure"
git push origin main
```

**GitHub Actions Process:**
1. **Checkout code** from repository
2. **Setup Terraform** (latest version)
3. **Configure AWS credentials** (from GitHub Secrets)
4. **Initialize backend** (`terraform init`)
5. **Validate syntax** (`terraform validate`)
6. **Format check** (`terraform fmt -check`)
7. **Generate plan** (`terraform plan`)
8. **Apply changes** (`terraform apply -auto-approve`)
9. **Display outputs** (connection details)

### Method 2: Local Deployment

**For development and testing:**

```bash
# 1. Navigate to terraform directory
cd terraform/

# 2. Initialize Terraform (downloads providers, configures backend)
terraform init

# 3. Plan the deployment (see what will be created)
terraform plan -var="aws_profile=m3"

# 4. Apply the changes (creates actual resources)
terraform apply -var="aws_profile=m3"
```

**Local Development Benefits:**
- **Faster feedback** - no CI/CD wait time
- **Debug capability** - can inspect state and troubleshoot
- **Partial deployments** - can target specific modules
- **State inspection** - can examine current infrastructure state

## Configuration

### Required Variables

Create a `terraform.tfvars` file with:

```hcl
# Basic Configuration
project_name = "text2agent"
environment  = "dev"
aws_region   = "eu-west-2"

# Local development only (not needed for GitHub Actions)
aws_profile = "m3"
```

### AWS Profile Setup (Local Only)

For local deployment, ensure your AWS profile is configured:

```bash
# Check if profile exists
aws configure list-profiles

# If 'm3' profile doesn't exist, create it:
aws configure --profile m3
```

## 🗄️ Database Architecture

### Two Databases in One Aurora Cluster

The system creates **one Aurora PostgreSQL cluster** with **two separate databases**:

#### 1. **str_kb Database** (Bedrock Knowledge Base)
```sql
Database: str_kb
└── Schema: bedrock_integration
    └── Table: bedrock_kb
        ├── id (UUID)
        ├── embedding (vector(1024))  ← HNSW indexed for fast similarity search
        ├── chunks (TEXT)
        └── metadata (JSON)
```

#### 2. **text2AgentTenants Database** (Multi-tenant Management)
```sql
Database: text2AgentTenants
├── Table: tenantmappings
│   ├── tenant_id (UUID)
│   ├── domain (VARCHAR)
│   └── bucket_name (VARCHAR)
└── Table: users
    ├── user_id (UUID)
    ├── email (VARCHAR)
    ├── tenant_id (UUID)
    └── cognito_sub (VARCHAR)
```

## AI/ML Components

### Amazon Bedrock Knowledge Base
- **Model**: Amazon Titan Text Embeddings v2
- **Vector Dimensions**: 1024
- **Storage**: Aurora PostgreSQL with pgvector
- **Index Type**: HNSW (Hierarchical Navigable Small World)
- **Purpose**: Fast semantic search over document embeddings

### Document Processing Flow
```
Documents (S3) → Bedrock → Embeddings → Aurora PostgreSQL → Search Results
```

## Security Features

- **VPC Isolation**: All resources in private subnets
- **IAM Roles**: Least-privilege access patterns
- **Secrets Manager**: Database credentials securely stored
- **Encryption**: 
  - Aurora: Encryption at rest
  - S3: Server-side encryption
  - Secrets: Encrypted with KMS

## What Gets Created

When you deploy, Terraform creates:

### Networking (6 resources)
- 1 VPC with DNS hostnames enabled
- 2 Public subnets (for NAT gateways)
- 2 Private subnets (for databases/apps)
- Route tables and NAT gateways

### Database (5 resources)
- 1 Aurora PostgreSQL cluster (`text2agent-dev-cluster`)
- 1 Aurora instance (serverless)
- 1 Secrets Manager secret (database credentials)
- 2 Databases with proper schemas and indexes

### AI/ML (2 resources)
- 1 Bedrock Knowledge Base
- 1 S3 Data Source connector

### Authentication (4 resources)
- 1 Cognito User Pool
- 1 Lambda function (post-confirmation)
- 1 Lambda layer (dependencies)
- IAM roles and policies

### Storage (1 resource)
- 1 S3 bucket (`str-data-store-bucket`)

**Total: ~25-30 AWS resources**

## ⚡ Terraform Commands Reference

### Basic Operations
```bash
# Initialize (required first time and after backend changes)
terraform init

# See what's currently deployed
terraform state list

# Check configuration syntax
terraform validate

# Format code (fixes indentation, style)
terraform fmt

# Check plan without applying (safe)
terraform plan -var="aws_profile=m3"

# Deploy everything
terraform apply -var="aws_profile=m3"

# Deploy with automatic approval (CI/CD)
terraform apply -var="aws_profile=m3" -auto-approve

# Destroy everything (⚠️ DESTRUCTIVE)
terraform destroy -var="aws_profile=m3"
```

### Advanced State Management
```bash
# List all resources in state
terraform state list

# Show detailed info about a resource
terraform state show aws_db_cluster.aurora_cluster

# Remove a resource from state (doesn't delete AWS resource)
terraform state rm aws_s3_bucket.example

# Import existing AWS resource into state
terraform import aws_s3_bucket.existing my-existing-bucket-name

# Move resource in state (useful for refactoring)
terraform state mv aws_s3_bucket.old aws_s3_bucket.new

# Refresh state with actual AWS resource status
terraform refresh -var="aws_profile=m3"

# Show current state in human-readable format
terraform show
```

### Targeted Operations
```bash
# Apply changes to specific resource only
terraform apply -target=aws_db_cluster.aurora_cluster -var="aws_profile=m3"

# Plan changes for specific module only
terraform plan -target=module.database -var="aws_profile=m3"

# Destroy specific resource only
terraform destroy -target=aws_s3_bucket.documents -var="aws_profile=m3"

# Apply changes to multiple specific resources
terraform apply -target=module.ai -target=module.database -var="aws_profile=m3"
```

### Debugging and Inspection
```bash
# Enable detailed logging
export TF_LOG=DEBUG
terraform apply -var="aws_profile=m3"

# Show outputs without applying
terraform output

# Show specific output value
terraform output aurora_cluster_endpoint

# Graph dependencies (requires graphviz)
terraform graph | dot -Tpng > graph.png

# Validate configuration with detailed errors
terraform validate -json
```

### Workspace Management (Multi-Environment)
```bash
# List all workspaces
terraform workspace list

# Create new workspace (for different environment)
terraform workspace new staging

# Switch to workspace
terraform workspace select production

# Show current workspace
terraform workspace show

# Delete workspace
terraform workspace delete staging
```

## 🔍 Accessing Your Infrastructure

After deployment, you'll get outputs with connection details:

```bash
# Example outputs:
aurora_cluster_endpoint = "text2agent-dev-cluster.cluster-xyz.eu-west-2.rds.amazonaws.com"
bedrock_knowledge_base_id = "ABC123XYZ"
cognito_user_pool_id = "eu-west-2_AbCdEfGhI"
s3_bucket_name = "str-data-store-bucket"
```

## Comprehensive Troubleshooting Guide

### Common Terraform Errors

#### 1. **Exit Code 3 (Formatting Issues)**
```bash
Error: Configuration formatting issues
```
**Fix:**
```bash
terraform fmt
terraform validate
```

#### 2. **State Lock Errors**
```bash
Error: Error acquiring the state lock
```
**Causes:**
- Another terraform process running
- Previous process crashed and left lock
- Network interruption during apply

**Fix:**
```bash
# List locks
terraform force-unlock LOCK_ID

# For S3 backend, check DynamoDB table for locks
aws dynamodb scan --table-name terraform-state-lock --profile m3
```

#### 3. **Backend Initialization Errors**
```bash
Error: Failed to get existing workspaces
```
**Fix:**
```bash
# Re-initialize backend
terraform init -reconfigure

# Force initialize (overwrites local state)
terraform init -force-copy
```

#### 4. **Provider Version Conflicts**
```bash
Error: Incompatible provider version
```
**Fix:**
```bash
# Upgrade providers to latest compatible versions
terraform init -upgrade

# Lock to specific versions (in versions.tf)
terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}
```

#### 5. **Resource Already Exists**
```bash
Error: Resource already exists
```
**Solutions:**
```bash
# Option 1: Import existing resource
terraform import aws_s3_bucket.example existing-bucket-name

# Option 2: Remove from state and let Terraform recreate
terraform state rm aws_s3_bucket.example

# Option 3: Rename resource in configuration
resource "aws_s3_bucket" "example_new" {
  # ... configuration
}
```

#### 6. **AWS Permission Errors**
```bash
Error: AccessDenied: User: arn:aws:iam::ACCOUNT:user/USERNAME is not authorized
```
**Debug steps:**
```bash
# Check current AWS identity
aws sts get-caller-identity --profile m3

# Test specific permissions
aws iam simulate-principal-policy \
  --policy-source-arn arn:aws:iam::994626600571:user/your-user \
  --action-names rds:CreateDBCluster \
  --resource-arns "*" \
  --profile m3

# Check IAM policies attached to user/role
aws iam list-attached-user-policies --user-name your-username --profile m3
```

### Aurora Database Issues

#### **HNSW Index Creation Failures**
```bash
Error: executing SQL: CREATE INDEX ... USING hnsw
```
**Debug:**
```bash
# Check pgvector version
psql -h YOUR_CLUSTER_ENDPOINT -U postgres -d str_kb -c "SELECT * FROM pg_available_extensions WHERE name = 'vector';"

# Check if index exists
psql -h YOUR_CLUSTER_ENDPOINT -U postgres -d str_kb -c "\\d bedrock_integration.bedrock_kb"

# Manually create index (for testing)
psql -h YOUR_CLUSTER_ENDPOINT -U postgres -d str_kb -c "CREATE INDEX ON bedrock_integration.bedrock_kb USING hnsw (embedding vector_cosine_ops);"
```

#### **Aurora Connection Timeouts**
```bash
Error: dial tcp: i/o timeout
```
**Causes & Fixes:**
- **VPC Security Groups**: Check inbound rules allow port 5432
- **Network ACLs**: Ensure subnet NACLs allow database traffic
- **Aurora Status**: Check cluster is in 'available' state
- **DNS Resolution**: Verify cluster endpoint resolves

```bash
# Test connectivity
telnet your-cluster-endpoint.region.rds.amazonaws.com 5432

# Check security groups
aws ec2 describe-security-groups --group-ids sg-xxxxxxxxx --profile m3

# Check Aurora cluster status
aws rds describe-db-clusters --db-cluster-identifier text2agent-dev-cluster --profile m3
```

### Bedrock Knowledge Base Issues

#### **Knowledge Base Creation Fails**
```bash
Error: ValidationException: The knowledge base storage configuration provided is invalid
```
**Common causes:**
1. **Missing HNSW index** in Aurora database
2. **Incorrect schema permissions**
3. **Vector column not found**

**Debug steps:**
```bash
# Verify database schema
psql -h ENDPOINT -U postgres -d str_kb -c "\\dt bedrock_integration.*"

# Check if HNSW index exists
psql -h ENDPOINT -U postgres -d str_kb -c "\\di bedrock_integration.*"

# Test vector operations
psql -h ENDPOINT -U postgres -d str_kb -c "SELECT embedding <=> '[1,2,3,4]'::vector FROM bedrock_integration.bedrock_kb LIMIT 1;"
```

### GitHub Actions Failures

#### **AWS Authentication Errors**
```yaml
Error: No credentials found
```
**Fix in GitHub Secrets:**
- `AWS_ACCESS_KEY_ID`: Your access key
- `AWS_SECRET_ACCESS_KEY`: Your secret key  
- `AWS_REGION`: `eu-west-2`

#### **Shell Compatibility Issues**
```bash
Error: [[: not found
```
**Cause**: GitHub Actions uses `/bin/sh` (dash), not bash
**Fix**: Use POSIX-compatible syntax:
```bash
# Instead of: [[ "$var" == *"pattern"* ]]
# Use: echo "$var" | grep -q "pattern"

# Instead of: [[ "$var" != "FAILED" ]]  
# Use: [ "$var" != "FAILED" ]
```

### Recovery Procedures

#### **Complete Infrastructure Recovery**
If infrastructure is corrupted:
```bash
# 1. Backup current state
cp terraform.tfstate terraform.tfstate.corrupted

# 2. Import all existing resources
terraform import aws_db_cluster.aurora_cluster text2agent-dev-cluster
terraform import aws_s3_bucket.documents str-data-store-bucket
# ... import other resources

# 3. Or destroy and recreate (if no critical data)
terraform destroy -var="aws_profile=m3"
terraform apply -var="aws_profile=m3"
```

#### **Partial Module Recovery**
If specific module fails:
```bash
# Target specific module for recreation
terraform destroy -target=module.ai -var="aws_profile=m3"
terraform apply -target=module.ai -var="aws_profile=m3"
```

#### **Database Recovery**
If Aurora cluster is corrupted:
```bash
# 1. Create manual snapshot first
aws rds create-db-cluster-snapshot \
  --db-cluster-snapshot-identifier "manual-backup-$(date +%Y%m%d)" \
  --db-cluster-identifier text2agent-dev-cluster \
  --profile m3

# 2. Then recreate with Terraform
terraform destroy -target=module.database -var="aws_profile=m3"
terraform apply -target=module.database -var="aws_profile=m3"
```

## Making Changes

### Safe Changes (Updates in-place)
- Adding tags to resources
- Modifying Lambda function code
- Updating IAM policies
- Adding new modules

### Dangerous Changes (Forces recreation)
- Changing VPC CIDR blocks
- Changing Aurora cluster identifier
- Modifying database names

**Always run `terraform plan` first to see what will change!**

## Operational Best Practices

### Development Workflow
```bash
# 1. Always plan first
terraform plan -var="aws_profile=m3" -out=plan.out

# 2. Review the plan carefully
terraform show plan.out

# 3. Apply the saved plan
terraform apply plan.out

# 4. Clean up plan file
rm plan.out
```

### Production Deployment
```bash
# 1. Use workspaces for environment separation
terraform workspace new production
terraform workspace select production

# 2. Use separate terraform.tfvars for each environment
terraform apply -var-file="production.tfvars"

# 3. Enable state locking with DynamoDB
# (already configured in backend.tf)

# 4. Use versioned modules
module "database" {
  source = "./modules/database"
  version = "v1.0.0"  # Pin to specific version
}
```# Test Lock Demo - Push 1
# Test Lock Demo - Push 2
