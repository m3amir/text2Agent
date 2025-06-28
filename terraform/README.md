# Text2Agent Terraform Infrastructure

Complete AWS infrastructure for the Text2Agent project - a production-ready Bedrock Knowledge Base system with Aurora PostgreSQL vector database and comprehensive state locking protection.

## 🔒 **State Locking & Concurrency Protection**

### **Overview**
This infrastructure uses **DynamoDB-based state locking** to prevent concurrent Terraform operations that could corrupt infrastructure state. The system automatically detects, analyzes, and handles both active and stale locks.

### **Lock Detection System**

#### **How It Works**
```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Workflow      │    │   DynamoDB       │    │   Decision      │
│   Starts        │───▶│   Lock Check     │───▶│   Engine        │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                                                         │
                              ┌──────────────────────────┼──────────────────────────┐
                              ▼                          ▼                          ▼
                    ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
                    │  No Locks       │    │  Active Lock    │    │  Stale Lock     │
                    │  ✅ Proceed     │    │  ❌ Block       │    │  ⏳ Approval   │
                    └─────────────────┘    └─────────────────┘    └─────────────────┘
```

#### **Lock States Explained**

**✅ No Locks Found**
- DynamoDB table empty or no relevant lock entries
- Workflow proceeds automatically
- Normal operation state

**❌ Active Lock Detected**
- Lock exists and is less than 30 minutes old
- OR lock is from a currently running GitHub Actions workflow  
- Workflow **immediately blocked** to prevent corruption
- Manual intervention required: wait for active operation to complete

**⏳ Stale Lock Detected**
- Lock exists but is older than 30 minutes
- OR lock is from a failed/cancelled workflow
- Workflow pauses for **manual approval** to remove stale lock
- Safe to approve if no other operations are running

### **Lock Detection Logic**

```bash
# Lock Age Analysis
if lock_age > 30_minutes:
    status = "stale"
elif github_workflow_still_running(lock.who):
    status = "active" 
elif lock.who contains "cancelled|failed|timeout":
    status = "stale"
elif lock_age < 10_minutes:
    status = "active" # Conservative approach
else:
    status = "stale"
```

### **DynamoDB Lock Table Structure**

**Table Name:** `text2agent-terraform-state-lock`  
**Region:** `eu-west-2`

**Lock Entry Format:**
```json
{
  "LockID": "text2agent-terraform-state-eu-west-2/text2agent/production/terraform.tfstate",
  "Info": {
    "ID": "unique-lock-id-12345",
    "Operation": "OperationTypePlan",
    "Who": "github-actions-runner-xyz",
    "Version": "1.5.7",
    "Created": "2024-01-15T10:30:00.000Z",
    "Path": "text2agent-terraform-state-eu-west-2/text2agent/production/terraform.tfstate"
  }
}
```

## 📋 **Scripts Reference**

### **Core Lock Management Scripts**

#### **1. `detect_and_handle_locks.sh`**
**Purpose:** Primary lock detection and analysis engine

**What it does:**
- Queries DynamoDB for existing lock entries
- Analyzes lock age and origin
- Determines if locks are active or stale
- Sets GitHub environment variables for workflow decisions
- Blocks workflows when active locks detected

**Usage:**
```bash
./detect_and_handle_locks.sh
# Exit code 0: No locks or stale locks found
# Exit code 1: Active locks detected - workflow should stop
```

**GitHub Environment Variables Set:**
- `STALE_LOCKS_FOUND`: true/false
- `ACTIVE_LOCKS_FOUND`: true/false  
- `LOCK_COUNT`: Number of locks found
- `LOCK_IDS`: Lock IDs for approval process
- `LOCK_DETAILS`: Formatted lock information for summaries

#### **2. `unlock_approved_locks.sh`**
**Purpose:** Removes stale locks after manual approval

**What it does:**
- Verifies AWS credentials and DynamoDB access
- Validates lock IDs match approval request
- Safely removes stale lock entries from DynamoDB
- Confirms successful removal

**Usage:**
```bash
# Requires LOCK_IDS environment variable
LOCK_IDS="lock-id-123" ./unlock_approved_locks.sh
```

**Safety Features:**
- Validates lock ID matches before removal
- Confirms lock removal with verification query
- Fails if lock changed since approval

#### **3. `setup_terraform_backend.sh`**
**Purpose:** Initializes S3 backend and DynamoDB locking infrastructure

**What it does:**
- Creates S3 bucket with versioning and encryption
- Creates DynamoDB table with proper schema
- Configures bucket security and access controls
- Generates backend configuration file
- Verifies permissions

**Creates:**
- S3 bucket: `text2agent-terraform-state-eu-west-2`
- DynamoDB table: `text2agent-terraform-state-lock`
- Backend config: `backend-override.tf`

#### **4. `build_psycopg2_layer.sh`** 
**Purpose:** Builds Linux-compatible Lambda layer using Docker

**What it does:**
- Uses AWS SAM Docker image for Python 3.11
- Compiles psycopg2-binary for Lambda runtime
- Creates properly structured layer zip file
- Optimizes layer size by removing unnecessary files

**Requirements:**
- Docker must be installed and running
- Uses `public.ecr.aws/sam/build-python3.11:latest` image

## 🔄 **GitHub Actions Workflow Integration**

### **Script Invocation Matrix**

The terraform infrastructure uses **4 core scripts** that are automatically invoked by GitHub Actions at specific points in the workflow. Here's exactly where each script is called:

#### **📋 Complete Script Invocation Breakdown**

| Script | Called In Job | Purpose | Frequency |
|--------|---------------|---------|-----------|
| `setup_terraform_backend.sh` | **6 jobs** | Initialize S3/DynamoDB backend | Before every terraform operation |
| `detect_and_handle_locks.sh` | **3 jobs** | Lock detection & analysis | At critical decision points |
| `unlock_approved_locks.sh` | **1 job** | Remove approved stale locks | Only after manual approval |
| `build_psycopg2_layer.sh` | **1 job** | Build Lambda dependencies | Once per workflow run |

### **Detailed Script Execution Flow**

#### **1. `setup_terraform_backend.sh` - Called 6 Times**

**This script runs BEFORE every terraform operation to ensure backend is ready:**

```yaml
# Job 1: terraform-check
- name: Setup Backend
  run: ./setup_terraform_backend.sh

# Job 2: stale-lock-check  
- name: Setup Backend
  run: ./setup_terraform_backend.sh

# Job 3: stale-lock-approval (conditional)
- name: Setup Backend
  run: ./setup_terraform_backend.sh

# Job 4: terraform-plan
- name: Setup Backend
  run: ./setup_terraform_backend.sh

# Job 5: terraform-apply
- name: Setup Backend
  run: ./setup_terraform_backend.sh

# Job 6: terraform-destroy (conditional)
- name: Setup Backend
  run: ./setup_terraform_backend.sh
```

**What it generates:**
- Creates `backend-override.tf` with S3 backend configuration
- Ensures DynamoDB lock table exists
- Verifies AWS permissions and connectivity

#### **2. `detect_and_handle_locks.sh` - Called 3 Times**

**Strategic lock detection at key workflow decision points:**

```yaml
# Call 1: stale-lock-check (Primary lock analysis)
- name: Check for Stale and Active Locks
  run: ./detect_and_handle_locks.sh
  # Sets: STALE_LOCKS_FOUND, ACTIVE_LOCKS_FOUND, LOCK_COUNT, LOCK_IDS

# Call 2: stale-lock-approval (Re-verification before approval)
- name: Get Lock Information  
  run: ./detect_and_handle_locks.sh
  # Confirms lock details for manual approval process

# Call 3: terraform-apply (Final safety check)
- name: Check for Stale Locks
  run: ./detect_and_handle_locks.sh
  # Last-chance protection before infrastructure changes
```

**GitHub Environment Variables Set:**
- `STALE_LOCKS_FOUND`: Controls approval workflow triggering
- `ACTIVE_LOCKS_FOUND`: Blocks workflow if active operations detected
- `LOCK_COUNT`: Used in approval summaries
- `LOCK_IDS`: Passed to unlock script for validation
- `LOCK_DETAILS`: Displayed in workflow summaries

#### **3. `unlock_approved_locks.sh` - Called 1 Time**

**Only executes after manual approval in GitHub environment:**

```yaml
# Job: stale-lock-approval (Conditional execution)
- name: Unlock Approved Locks
  run: ./unlock_approved_locks.sh
  # Requires: LOCK_IDS environment variable from detect script
  # Only runs: After human approval in GitHub environment
```

**Execution Flow:**
```
Stale Lock Detected → GitHub Environment Approval → Script Executes → Locks Removed
```

#### **4. `build_psycopg2_layer.sh` - Called 1 Time**

**Lambda dependency compilation - runs once per workflow:**

```yaml
# Job: build-lambda (First job, no terraform interaction)
- name: Build psycopg2 Layer
  run: ./build_psycopg2_layer.sh
  # Creates: psycopg2-layer.zip for Lambda functions
  # Uploaded: As workflow artifact for later jobs
```

### **Terraform Configuration Integration**

#### **Backend Configuration Auto-Generation**

The terraform configuration **does NOT directly reference** the scripts, but depends on their output:

**In `main.tf` (line 32):**
```hcl
# This file is auto-generated by setup_terraform_backend.sh
```

**Generated `backend-override.tf`:**
```hcl
terraform {
  backend "s3" {
    bucket         = "text2agent-terraform-state-eu-west-2"
    key            = "text2agent/production/terraform.tfstate"
    region         = "eu-west-2"
    dynamodb_table = "text2agent-terraform-state-lock"
    encrypt        = true
  }
}
```

#### **Script-to-Terraform Interaction Pattern**

```
┌─────────────────────┐    ┌─────────────────────┐    ┌─────────────────────┐
│   GitHub Actions   │    │   Shell Scripts     │    │   Terraform Core   │
│   Workflow Jobs    │───▶│   (Infrastructure)  │───▶│   (Configuration)   │
└─────────────────────┘    └─────────────────────┘    └─────────────────────┘
         │                            │                            │
         │                            ▼                            │
         │              ┌─────────────────────┐                    │
         │              │   AWS Resources     │                    │
         │              │   (S3, DynamoDB)    │◀───────────────────┘
         │              └─────────────────────┘
         │                            │
         ▼                            ▼
┌─────────────────────┐    ┌─────────────────────┐
│   Workflow Control  │    │   State Locking     │
│   (Job Dependencies)│    │   (Concurrency)     │
└─────────────────────┘    └─────────────────────┘
```

### **Workflow Jobs & Lock Integration**

#### **1. `build-lambda`**
- **Scripts Called:** `build_psycopg2_layer.sh`
- **Terraform Interaction:** None (pure build job)
- **Output:** Lambda artifacts for deployment

#### **2. `terraform-check`**
- **Scripts Called:** `setup_terraform_backend.sh`
- **Terraform Commands:** `init`, `validate`, `fmt -check`
- **Purpose:** Syntax validation and backend initialization

#### **3. `stale-lock-check`**
- **Scripts Called:** `setup_terraform_backend.sh`, `detect_and_handle_locks.sh`
- **Terraform Commands:** `init -reconfigure`
- **Decision Point:** Determines workflow continuation

#### **4. `stale-lock-approval` (conditional)**
- **Scripts Called:** `setup_terraform_backend.sh`, `detect_and_handle_locks.sh`, `unlock_approved_locks.sh`
- **Terraform Commands:** `init -reconfigure`
- **Trigger Condition:** `stale_locks_found == 'true' && active_locks_found != 'true'`

#### **5. `terraform-plan`**
- **Scripts Called:** `setup_terraform_backend.sh`
- **Terraform Commands:** `init`, `plan -out=tfplan`
- **Dependencies:** Successful lock check completion

#### **6. `terraform-apply`**
- **Scripts Called:** `setup_terraform_backend.sh`, `detect_and_handle_locks.sh`
- **Terraform Commands:** `init`, `apply -auto-approve tfplan`
- **Protection:** Final lock check before infrastructure changes

#### **7. `terraform-destroy` (conditional)**
- **Scripts Called:** `setup_terraform_backend.sh`
- **Terraform Commands:** `init`, `plan -destroy`, `apply destroy-plan`
- **Trigger:** Manual workflow dispatch with `action == 'destroy'`

### **Workflow Decision Tree**
```
Workflow Start
     │
     ▼
┌─────────────┐
│ Lock Check  │
└─────────────┘
     │
     ▼
┌─────────────┐    No Locks     ┌──────────────┐
│   Result    │ ──────────────▶ │   Proceed    │
│   Analysis  │                 │   Normally   │
└─────────────┘                 └──────────────┘
     │
     │ Active Locks
     ▼
┌─────────────┐
│    STOP     │
│  Workflow   │
└─────────────┘
     │
     │ Stale Locks  
     ▼
┌─────────────┐    Manual      ┌──────────────┐
│  Approval   │ ──────────────▶│   Unlock &   │
│  Required   │    Approval    │   Proceed    │
└─────────────┘                └──────────────┘
```

## 🏗️ **Infrastructure Components**

### **Core AWS Resources**

#### **Networking**
- **VPC:** Custom VPC with public and private subnets
- **Availability Zones:** Multi-AZ deployment (eu-west-2a, eu-west-2b)
- **Security Groups:** Least-privilege access controls
- **NAT Gateway:** Secure internet access for private subnets

#### **Database**
- **Aurora Serverless V2:** PostgreSQL 15.4 with vector extension
- **Auto-pause:** Configurable auto-pause after 15 minutes inactivity
- **Scaling:** min_capacity=0, max_capacity=1 ACU
- **Databases:** 
  - `str_kb`: Bedrock Knowledge Base vector storage
  - `text2Agent-Tenants`: User and tenant management

#### **Authentication**
- **Cognito User Pool:** User authentication and management
- **Lambda Triggers:** Post-confirmation user processing
- **Domain:** Custom authentication domain

#### **AI & Search**
- **Bedrock Knowledge Base:** Document indexing and vector search
- **S3 Data Source:** Document storage and ingestion
- **Titan Embeddings:** 1024-dimensional vector embeddings

#### **Storage**
- **S3 Bucket:** Document storage with encryption
- **Versioning:** Enabled for data protection
- **Lifecycle:** Automated data management

## 🚨 **Troubleshooting**

### **Common Lock Issues**

#### **"Active Locks Detected" Error**
```
❌ ACTIVE LOCKS DETECTED - WORKFLOW BLOCKED
```

**Cause:** Another Terraform operation is currently running
**Solution:**
1. Check GitHub Actions for running workflows
2. Wait for active operation to complete
3. Re-run your workflow

**Manual Check:**
```bash
aws dynamodb scan \
  --table-name text2agent-terraform-state-lock \
  --region eu-west-2 \
  --profile m3
```

#### **"Stale Locks Detected" - Approval Required**
```
❌ STALE LOCKS DETECTED - APPROVAL REQUIRED
```

**Cause:** Previous workflow failed/cancelled leaving stale lock
**Solution:**
1. Review lock details in workflow summary
2. Verify no other operations running
3. Approve lock removal in GitHub environment
4. Workflow continues automatically

#### **Lock Table Access Errors**
```
❌ DynamoDB table not accessible
```

**Causes & Solutions:**
- **Missing Permissions:** Verify AWS profile `m3` has DynamoDB access
- **Wrong Region:** Ensure using `eu-west-2`
- **Table Missing:** Run `setup_terraform_backend.sh` to create table

### **Backend Issues**

#### **State File Corruption**
If state becomes corrupted, restore from backup:
```bash
# List available backups
aws s3 ls s3://text2agent-terraform-state-eu-west-2/backups/ --profile m3

# Restore from backup
aws s3 cp \
  s3://text2agent-terraform-state-eu-west-2/backups/pre-apply-terraform.tfstate.TIMESTAMP \
  s3://text2agent-terraform-state-eu-west-2/text2agent/production/terraform.tfstate \
  --profile m3
```

#### **Backend Initialization Errors**
```bash
# Recreate backend configuration
./setup_terraform_backend.sh

# Force backend reconfiguration
terraform init -reconfigure
```

## 🔧 **Manual Operations**

### **Local Development**

#### **Prerequisites**
```bash
# Required tools
aws-cli (configured with profile 'm3')
terraform v1.5.7
docker (for Lambda layer builds)
```

#### **Setup Local Backend**
```bash
cd terraform
./setup_terraform_backend.sh
terraform init
```

#### **Check Infrastructure State**
```bash
# Check for locks before operations
./detect_and_handle_locks.sh

# Plan changes
terraform plan -var="aws_region=eu-west-2" -var="aws_profile=m3"

# Apply changes (use carefully)
terraform apply -var="aws_region=eu-west-2" -var="aws_profile=m3"
```

### **Testing Lock System**

#### **Test Lock Detection**
```bash
# Should return success (exit 0) when no locks
./detect_and_handle_locks.sh
echo $?  # Should print 0

# Create test lock to verify detection
aws dynamodb put-item \
  --table-name text2agent-terraform-state-lock \
  --item '{"LockID":{"S":"test-lock"},"Info":{"S":"{\"ID\":\"test123\",\"Who\":\"manual-test\"}"}}' \
  --region eu-west-2 \
  --profile m3

# Should detect the test lock
./detect_and_handle_locks.sh

# Clean up test lock
aws dynamodb delete-item \
  --table-name text2agent-terraform-state-lock \
  --key '{"LockID":{"S":"test-lock"}}' \
  --region eu-west-2 \
  --profile m3
```

```

### **Development Workflow**
1. Make changes to `.tf` files
2. Test locally: `terraform plan`
3. Commit and push to trigger GitHub Actions
4. Monitor workflow execution
5. Review deployment results

The infrastructure is now protected against concurrent modifications and ready for production use! 🎉
