# 🚀 Text2Agent Deployment Guide

Quick guide to deploy your Bedrock Knowledge Base infrastructure.

## 🎯 What This Deploys

- **Aurora PostgreSQL** database with vector search (pgvector)
- **Amazon Bedrock** Knowledge Base with Titan embeddings
- **S3 bucket** for document storage
- **Cognito** user authentication
- **Lambda functions** for user management
- **VPC** with secure networking

## ⚡ Quick Deploy (Recommended)

### Method 1: GitHub Actions (Zero Setup)

Just push to main branch - that's it! 

```bash
git add .
git commit -m "Deploy infrastructure"
git push origin main
```

GitHub Actions will automatically:
1. Run Terraform validation
2. Deploy all AWS resources  
3. Set up the databases with proper indexes
4. Configure Bedrock Knowledge Base
5. Provide you with connection details

### Method 2: Local Deploy

For testing or development:

```bash
# 1. Go to terraform directory
cd terraform/

# 2. See what will be created
terraform plan -var="aws_profile=m3"

# 3. Deploy it
terraform apply -var="aws_profile=m3"
```

## 📋 What You Get

After deployment you'll have:

### 🗄️ Databases
- **Cluster**: `text2agent-dev-cluster`
- **Database 1**: `str_kb` (for Bedrock vector embeddings)
- **Database 2**: `text2AgentTenants` (for user/tenant management)

### 🧠 AI Components  
- **Bedrock Knowledge Base**: Ready for document search
- **S3 Bucket**: `str-data-store-bucket` (upload documents here)
- **Vector Search**: 1024-dimension embeddings with HNSW indexing

### 🔐 Authentication
- **Cognito User Pool**: User registration/login
- **Lambda Functions**: User management automation

## 🔧 Configuration

No configuration needed for GitHub Actions! 

For local deployment, just ensure AWS profile `m3` exists:
```bash
aws configure --profile m3
```

## 📊 Resources Created

- **Total AWS resources**: ~25-30
- **Estimated monthly cost**: $90-215
- **Deployment time**: ~15-20 minutes
- **Regions supported**: eu-west-2 (London)

## 🐛 If Something Goes Wrong

1. **Check GitHub Actions logs** for detailed error messages
2. **Formatting issues**: Run `terraform fmt` in the terraform/ directory
3. **Permission issues**: Verify AWS credentials are properly configured

## 📖 Detailed Documentation

For complete documentation, see: [`terraform/README.md`](terraform/README.md)

## 🎉 Next Steps After Deployment

1. **Upload documents** to your S3 bucket
2. **Test Bedrock** through AWS Console
3. **Configure your app** to use the deployed resources
4. **Create users** in Cognito User Pool

---

**Ready to deploy?** Just push to GitHub and watch the magic happen! ✨ 