# GitHub Actions Workflows

This directory contains GitHub Actions workflows for deploying infrastructure and applications.

## Workflows

### 1. `deploy.yml` - Full Stack Deployment
- **Purpose**: Deploys both infrastructure (Terraform) and application (Elastic Beanstalk)
- **Triggers**: Push to main branch
- **Order**: Test → Terraform → Deploy → Cleanup (on failure)

### 2. `terraform.yml` - Infrastructure Only
- **Purpose**: Manages Terraform infrastructure independently
- **Triggers**: 
  - Push to main/feature/IAC branches (when terraform files change)
  - Pull requests to main (when terraform files change)
  - Manual dispatch with action choice (plan/apply/destroy)

## Required GitHub Secrets

Set these in your repository settings:

```bash
AWS_ACCESS_KEY_ID          # AWS Access Key for deployment
AWS_SECRET_ACCESS_KEY      # AWS Secret Key for deployment
AWS_REGION                 # AWS Region (defaults to us-west-2)
ELASTIC_BEANSTALK_APP_NAME # EB Application Name
ELASTIC_BEANSTALK_ENV_NAME # EB Environment Name
```

## Current Infrastructure

Based on your Terraform configuration, these workflows will deploy:

### 🗄️ **Databases (Aurora Serverless v2)**
- **Main App Database**: `text2agent` (min ACU: 0, max ACU: 2)
- **Bedrock Knowledge Base**: `str-knowledge-base` (min ACU: 0, max ACU: 2)

### 🪣 **Storage**
- **S3 Bucket**: `str-data-store-bucket`

### 🧠 **AI/ML**
- **Bedrock Knowledge Base**: Vector database with semantic chunking
- **Data Source**: S3 integration for document processing

### 🔐 **Security**
- **Secrets Manager**: Database credentials
- **IAM Roles**: Service-specific permissions
- **VPC**: Private networking with public/private subnets

## Usage Examples

### Deploy Everything (Infrastructure + App)
```bash
git push origin main
```

### Deploy Only Infrastructure
1. **Via Push**:
   ```bash
   git add terraform/
   git commit -m "Update infrastructure"
   git push origin feature/IAC
   ```

2. **Via Manual Trigger**:
   - Go to Actions tab in GitHub
   - Select "Deploy Terraform Infrastructure"
   - Click "Run workflow"
   - Choose action: plan/apply/destroy

### Review Infrastructure Changes
1. Create PR with terraform changes
2. Workflow will automatically comment with plan
3. Review the plan before merging

## Workflow Features

### 🔍 **Safety Features**
- Format checking and validation
- Plan before apply
- PR plan comments
- Cleanup on failure
- Manual approval for destructive operations

### 📊 **Monitoring**
- Step summaries with key resource info
- Artifact uploads for plans and outputs
- Infrastructure output sharing between jobs

### 🔧 **Flexibility**
- Manual triggers for all operations
- Environment-specific configurations
- Conditional execution based on branch/changes

## File Structure

```
.github/workflows/
├── deploy.yml      # Full deployment pipeline
├── terraform.yml   # Infrastructure-only pipeline
└── README.md       # This documentation
```

## Next Steps

1. **Set up secrets** in GitHub repository settings
2. **Test the workflow** with a small change
3. **Review outputs** in Actions tab after deployment
4. **Monitor costs** in AWS console (Aurora Serverless scales to 0) 