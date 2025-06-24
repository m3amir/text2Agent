# 🏭 Production Deployment Guide

## 🎯 Overview
This guide covers safe production deployment practices that avoid destructive operations.

## 🔧 Prerequisites

### 1. Remote State Configuration
```hcl
# In terraform.tf, uncomment and configure:
terraform {
  backend "s3" {
    bucket         = "your-company-terraform-state"
    key            = "text2agent/prod/terraform.tfstate"
    region         = "eu-west-2"
    encrypt        = true
    dynamodb_table = "terraform-state-lock"
  }
}
```

### 2. Environment Variables
Set these GitHub repository variables:
- `ENVIRONMENT` = `prod`
- `AWS_REGION` = `eu-west-2`

## 🚀 Production Deployment Steps

### Phase 1: Import Existing Resources (If Any)

If resources already exist, import them instead of recreating:

```bash
# 1. Import IAM Roles
terraform import aws_iam_role.bedrock_kb_role text2agent-prod-bedrock-kb-role
terraform import aws_iam_role.rds_enhanced_monitoring text2agent-prod-rds-monitoring-role
terraform import aws_iam_role.lambda_execution_role text2agent-prod-lambda-role

# 2. Import IAM Policies (replace ACCOUNT_ID)
terraform import aws_iam_policy.bedrock_model_policy arn:aws:iam::ACCOUNT_ID:policy/text2agent-prod-bedrock-model-policy
terraform import aws_iam_policy.bedrock_rds_policy arn:aws:iam::ACCOUNT_ID:policy/text2agent-prod-bedrock-rds-policy

# 3. Import VPC Resources (replace vpc-xxx with actual IDs)
terraform import aws_vpc.main vpc-xxxxxxxxx
terraform import aws_subnet.private.0 subnet-xxxxxxxxx
terraform import aws_subnet.public.0 subnet-xxxxxxxxx

# 4. Import RDS Resources
terraform import aws_db_subnet_group.main text2agent-prod-db-subnet-group
terraform import aws_rds_cluster.main text2agent-prod-aurora-cluster
```

### Phase 2: Plan and Validate
```bash
terraform plan -var="environment=prod" -var="aws_region=eu-west-2"
```

### Phase 3: Gradual Apply
```bash
# Apply infrastructure in stages
terraform apply -target=aws_vpc.main
terraform apply -target=aws_rds_cluster.main
terraform apply # Full apply
```

## 🛡️ Safety Measures

### Resource Protection
```hcl
# Add to critical resources:
lifecycle {
  prevent_destroy = true
}
```

### Blue-Green Deployments
- Use separate environments: `prod-blue`, `prod-green`
- Switch traffic after validation
- Keep rollback capability

### Backup Strategy
- RDS automated backups: 30 days retention
- S3 versioning enabled
- Cross-region backup for critical data

## 🚨 Emergency Procedures

### Rollback Plan
1. **Database**: Point-in-time recovery available
2. **Infrastructure**: Use previous Terraform state
3. **Application**: Deploy previous version

### Incident Response
1. **Stop destructive operations**
2. **Assess impact scope**
3. **Communicate with team**
4. **Execute recovery plan**

## 📊 Monitoring

### Required Alerts
- RDS connection failures
- S3 access errors
- Lambda execution failures
- VPC connectivity issues

### Health Checks
- Database connectivity
- Application endpoints
- Resource quota monitoring

## 🎛️ Environment Management

### Development
- Allows resource cleanup
- Fast iteration
- Cost optimization

### Staging
- Production-like configuration
- Full integration testing
- Performance validation

### Production
- No destructive cleanup
- Import-based management
- Change control process

## 🔄 CI/CD Best Practices

### Pipeline Stages
1. **Validate**: Terraform fmt, validate, plan
2. **Security**: Policy checks, credential scanning
3. **Deploy**: Environment-specific deployment
4. **Test**: Post-deployment validation
5. **Monitor**: Health check verification

### Manual Approval Gates
- Production deployments require approval
- Database changes require approval
- Infrastructure changes require approval

## 📋 Checklist

### Pre-Deployment
- [ ] Backup verification
- [ ] Team notification
- [ ] Maintenance window scheduled
- [ ] Rollback plan confirmed

### Post-Deployment
- [ ] Health checks passing
- [ ] Monitoring active
- [ ] Performance baseline established
- [ ] Documentation updated

## 🎯 Key Differences from Development

| Aspect | Development | Production |
|--------|-------------|------------|
| Resource Cleanup | ✅ Automatic | ❌ Manual Only |
| State Management | Local | Remote (S3) |
| Backup Retention | 7 days | 30+ days |
| Change Approval | None | Required |
| Monitoring | Basic | Comprehensive |
| Rollback Testing | Optional | Mandatory |

## 🚀 Getting Started

1. **Set up remote state backend**
2. **Configure production variables**
3. **Import existing resources**
4. **Run plan to verify**
5. **Apply with approval gates**
6. **Validate deployment**
7. **Enable monitoring**

This approach ensures zero-downtime deployments and maintains production stability! 🎯 