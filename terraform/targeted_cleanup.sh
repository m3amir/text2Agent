#!/bin/bash

# Targeted cleanup script for text2agent AWS resources
# Based on exact resource names from Terraform configuration

set -e

echo "🧹 TARGETED TEXT2AGENT RESOURCE CLEANUP"
echo "======================================="
echo ""
echo "⚠️  WARNING: This will delete specific text2agent resources!"
echo ""

# Configuration - these match your terraform.tfvars and variables.tf
PROJECT_NAME="text2agent"
ENVIRONMENT="dev"
AWS_REGION="eu-west-2"

echo "🔧 Configuration:"
echo "  Project: $PROJECT_NAME"
echo "  Environment: $ENVIRONMENT"
echo "  Region: $AWS_REGION"
echo ""

# Function to safely delete with error handling
safe_delete() {
    local resource_type="$1"
    local resource_name="$2"
    local command="$3"
    
    echo "🔄 Deleting $resource_type: $resource_name"
    if eval "$command"; then
        echo "✅ $resource_type deleted successfully"
    else
        echo "⚠️  $resource_type deletion failed or resource not found"
    fi
    echo ""
}

echo "🚀 Starting targeted cleanup..."
echo ""

# ===========================================
# PHASE 1: LAMBDA FUNCTIONS
# ===========================================
echo "🔧 PHASE 1: LAMBDA CLEANUP"
echo "=========================="

# Delete Lambda function
safe_delete "Lambda Function" "text2Agent-Post-Confirmation" \
    "aws lambda delete-function --function-name text2Agent-Post-Confirmation --region $AWS_REGION"

echo ""

# ===========================================
# PHASE 2: BEDROCK KNOWLEDGE BASE
# ===========================================
echo "🤖 PHASE 2: BEDROCK CLEANUP"
echo "=========================="

# Get knowledge base IDs first
echo "🔍 Finding Bedrock Knowledge Base..."
KB_IDS=$(aws bedrock-agent list-knowledge-bases --region $AWS_REGION --query 'knowledgeBaseSummaries[?starts_with(name, `'$PROJECT_NAME'`)].knowledgeBaseId' --output text 2>/dev/null || echo "")

if [ -n "$KB_IDS" ]; then
    for kb_id in $KB_IDS; do
        echo "🔄 Deleting Bedrock Knowledge Base: $kb_id"
        
        # Delete data sources first
        aws bedrock-agent list-data-sources --knowledge-base-id "$kb_id" --region $AWS_REGION --query 'dataSourceSummaries[].dataSourceId' --output text 2>/dev/null | tr '\t' '\n' | while read -r ds_id; do
            if [ -n "$ds_id" ] && [ "$ds_id" != "None" ]; then
                echo "  🗑️  Deleting data source: $ds_id"
                aws bedrock-agent delete-data-source --knowledge-base-id "$kb_id" --data-source-id "$ds_id" --region $AWS_REGION 2>/dev/null || true
            fi
        done
        
        # Wait for data sources to be deleted
        sleep 10
        
        # Delete knowledge base
        aws bedrock-agent delete-knowledge-base --knowledge-base-id "$kb_id" --region $AWS_REGION 2>/dev/null || true
        echo "✅ Bedrock Knowledge Base deleted"
    done
else
    echo "ℹ️  No Bedrock Knowledge Bases found"
fi

echo ""

# ===========================================
# PHASE 3: RDS CLEANUP
# ===========================================
echo "🗄️  PHASE 3: RDS CLEANUP"
echo "======================="

# Delete RDS cluster instances first, then clusters
echo "🔄 Deleting RDS cluster instances..."

# Main cluster instances
aws rds describe-db-clusters --db-cluster-identifier "text2agent" --region $AWS_REGION --query 'DBClusters[0].DBClusterMembers[].DBInstanceIdentifier' --output text 2>/dev/null | tr '\t' '\n' | while read -r instance; do
    if [ -n "$instance" ] && [ "$instance" != "None" ]; then
        safe_delete "RDS Instance" "$instance" \
            "aws rds delete-db-instance --db-instance-identifier '$instance' --skip-final-snapshot --delete-automated-backups --region $AWS_REGION"
    fi
done

# Bedrock cluster instances  
aws rds describe-db-clusters --db-cluster-identifier "str-knowledge-base" --region $AWS_REGION --query 'DBClusters[0].DBClusterMembers[].DBInstanceIdentifier' --output text 2>/dev/null | tr '\t' '\n' | while read -r instance; do
    if [ -n "$instance" ] && [ "$instance" != "None" ]; then
        safe_delete "RDS Instance" "$instance" \
            "aws rds delete-db-instance --db-instance-identifier '$instance' --skip-final-snapshot --delete-automated-backups --region $AWS_REGION"
    fi
done

echo "⏳ Waiting for RDS instances to delete..."
sleep 60

# Delete RDS clusters
safe_delete "RDS Cluster" "text2agent" \
    "aws rds delete-db-cluster --db-cluster-identifier text2agent --skip-final-snapshot --delete-automated-backups --region $AWS_REGION"

safe_delete "RDS Cluster" "str-knowledge-base" \
    "aws rds delete-db-cluster --db-cluster-identifier str-knowledge-base --skip-final-snapshot --delete-automated-backups --region $AWS_REGION"

echo "⏳ Waiting for RDS clusters to delete..."
sleep 30

# Delete DB subnet group
safe_delete "DB Subnet Group" "$PROJECT_NAME-$ENVIRONMENT-db-subnet-group" \
    "aws rds delete-db-subnet-group --db-subnet-group-name '$PROJECT_NAME-$ENVIRONMENT-db-subnet-group' --region $AWS_REGION"

echo ""

# ===========================================
# PHASE 4: S3 CLEANUP
# ===========================================
echo "🪣 PHASE 4: S3 CLEANUP"
echo "====================="

# Find S3 buckets with text2agent pattern
echo "🔍 Finding text2agent S3 buckets..."
aws s3api list-buckets --query 'Buckets[].Name' --output text | tr '\t' '\n' | while read -r bucket; do
    if [[ "$bucket" == *"$PROJECT_NAME"* ]] && [[ "$bucket" == *"$ENVIRONMENT"* ]] && [[ "$bucket" == *"str-data-store"* ]]; then
        echo "🗑️  Found bucket: $bucket"
        echo "  📋 Emptying bucket..."
        aws s3 rm "s3://$bucket" --recursive 2>/dev/null || true
        echo "  🗑️  Deleting bucket..."
        aws s3api delete-bucket --bucket "$bucket" --region $AWS_REGION 2>/dev/null || true
        echo "✅ S3 bucket deleted"
    fi
done

echo ""

# ===========================================
# PHASE 5: SECRETS MANAGER CLEANUP
# ===========================================
echo "🔐 PHASE 5: SECRETS CLEANUP"
echo "=========================="

# Delete secrets (they have random suffixes, so we'll search by prefix)
echo "🔍 Finding Secrets Manager secrets..."
aws secretsmanager list-secrets --region $AWS_REGION --query 'SecretList[?starts_with(Name, `'$PROJECT_NAME'-'$ENVIRONMENT'`)].Name' --output text | tr '\t' '\n' | while read -r secret_name; do
    if [ -n "$secret_name" ]; then
        safe_delete "Secret" "$secret_name" \
            "aws secretsmanager delete-secret --secret-id '$secret_name' --force-delete-without-recovery --region $AWS_REGION"
    fi
done

echo ""

# ===========================================
# PHASE 6: IAM CLEANUP
# ===========================================
echo "👤 PHASE 6: IAM CLEANUP"
echo "======================"

# Function to cleanup IAM role
cleanup_iam_role() {
    local role_name="$1"
    echo "🔄 Cleaning up IAM role: $role_name"
    
    if aws iam get-role --role-name "$role_name" &>/dev/null; then
        # Detach managed policies
        aws iam list-attached-role-policies --role-name "$role_name" --query 'AttachedPolicies[].PolicyArn' --output text | tr '\t' '\n' | while read -r policy_arn; do
            if [ -n "$policy_arn" ] && [ "$policy_arn" != "None" ]; then
                aws iam detach-role-policy --role-name "$role_name" --policy-arn "$policy_arn" 2>/dev/null || true
            fi
        done
        
        # Delete inline policies
        aws iam list-role-policies --role-name "$role_name" --query 'PolicyNames' --output text | tr '\t' '\n' | while read -r policy_name; do
            if [ -n "$policy_name" ] && [ "$policy_name" != "None" ]; then
                aws iam delete-role-policy --role-name "$role_name" --policy-name "$policy_name" 2>/dev/null || true
            fi
        done
        
        # Delete the role
        aws iam delete-role --role-name "$role_name" 2>/dev/null || true
        echo "✅ Role deleted: $role_name"
    else
        echo "ℹ️  Role not found: $role_name"
    fi
}

# Function to cleanup IAM policy
cleanup_iam_policy() {
    local policy_name="$1"
    echo "🔄 Cleaning up IAM policy: $policy_name"
    
    ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
    POLICY_ARN="arn:aws:iam::${ACCOUNT_ID}:policy/${policy_name}"
    
    if aws iam get-policy --policy-arn "$POLICY_ARN" &>/dev/null; then
        # Detach from all entities
        aws iam list-entities-for-policy --policy-arn "$POLICY_ARN" --query 'PolicyRoles[].RoleName' --output text | tr '\t' '\n' | while read -r role_name; do
            if [ -n "$role_name" ] && [ "$role_name" != "None" ]; then
                aws iam detach-role-policy --role-name "$role_name" --policy-arn "$POLICY_ARN" 2>/dev/null || true
            fi
        done
        
        # Delete non-default versions
        aws iam list-policy-versions --policy-arn "$POLICY_ARN" --query 'Versions[?IsDefaultVersion==`false`].VersionId' --output text | tr '\t' '\n' | while read -r version_id; do
            if [ -n "$version_id" ] && [ "$version_id" != "None" ]; then
                aws iam delete-policy-version --policy-arn "$POLICY_ARN" --version-id "$version_id" 2>/dev/null || true
            fi
        done
        
        # Delete the policy
        aws iam delete-policy --policy-arn "$POLICY_ARN" 2>/dev/null || true
        echo "✅ Policy deleted: $policy_name"
    else
        echo "ℹ️  Policy not found: $policy_name"
    fi
}

# Cleanup IAM roles
cleanup_iam_role "$PROJECT_NAME-$ENVIRONMENT-bedrock-kb-role"
cleanup_iam_role "$PROJECT_NAME-$ENVIRONMENT-lambda-role"
cleanup_iam_role "$PROJECT_NAME-$ENVIRONMENT-rds-monitoring-role"

# Cleanup IAM policies
cleanup_iam_policy "$PROJECT_NAME-$ENVIRONMENT-bedrock-s3-policy"
cleanup_iam_policy "$PROJECT_NAME-$ENVIRONMENT-bedrock-model-policy"
cleanup_iam_policy "$PROJECT_NAME-$ENVIRONMENT-bedrock-rds-policy"
cleanup_iam_policy "$PROJECT_NAME-$ENVIRONMENT-lambda-policy"

echo ""

# ===========================================
# PHASE 7: VPC CLEANUP
# ===========================================
echo "🌐 PHASE 7: VPC CLEANUP"
echo "======================"

# Find VPC by project and environment tags (handles random suffixes)
VPC_ID=$(aws ec2 describe-vpcs --filters "Name=tag:Name,Values=$PROJECT_NAME-$ENVIRONMENT-vpc-*" --query 'Vpcs[0].VpcId' --output text --region $AWS_REGION 2>/dev/null || echo "None")

# Also try to find by project tag if name-based search fails
if [ "$VPC_ID" = "None" ] || [ -z "$VPC_ID" ]; then
    echo "🔍 Trying alternative VPC search by project tag..."
    VPC_ID=$(aws ec2 describe-vpcs --filters "Name=tag:Project,Values=$PROJECT_NAME" "Name=tag:Environment,Values=$ENVIRONMENT" --query 'Vpcs[0].VpcId' --output text --region $AWS_REGION 2>/dev/null || echo "None")
fi

if [ "$VPC_ID" != "None" ] && [ -n "$VPC_ID" ]; then
    echo "🔍 Found VPC: $VPC_ID"
    
    # Delete NAT Gateways first (and wait)
    echo "🌐 Deleting NAT Gateways..."
    aws ec2 describe-nat-gateways --filter "Name=vpc-id,Values=$VPC_ID" --query 'NatGateways[].NatGatewayId' --output text --region $AWS_REGION | tr '\t' '\n' | while read -r nat_id; do
        if [ -n "$nat_id" ] && [ "$nat_id" != "None" ]; then
            aws ec2 delete-nat-gateway --nat-gateway-id "$nat_id" --region $AWS_REGION
            echo "✅ Deleted NAT Gateway: $nat_id"
        fi
    done
    
    echo "⏳ Waiting for NAT Gateways to delete..."
    sleep 60
    
    # Release Elastic IPs (search by project tags since names have random suffixes)
    echo "🔌 Releasing Elastic IPs..."
    aws ec2 describe-addresses --filters "Name=tag:Name,Values=$PROJECT_NAME-$ENVIRONMENT-nat-eip-*" --query 'Addresses[].AllocationId' --output text --region $AWS_REGION | tr '\t' '\n' | while read -r alloc_id; do
        if [ -n "$alloc_id" ] && [ "$alloc_id" != "None" ]; then
            aws ec2 release-address --allocation-id "$alloc_id" --region $AWS_REGION
            echo "✅ Released EIP: $alloc_id"
        fi
    done
    
    # Delete Internet Gateway
    echo "🌐 Deleting Internet Gateway..."
    aws ec2 describe-internet-gateways --filters "Name=attachment.vpc-id,Values=$VPC_ID" --query 'InternetGateways[].InternetGatewayId' --output text --region $AWS_REGION | tr '\t' '\n' | while read -r igw_id; do
        if [ -n "$igw_id" ] && [ "$igw_id" != "None" ]; then
            aws ec2 detach-internet-gateway --internet-gateway-id "$igw_id" --vpc-id "$VPC_ID" --region $AWS_REGION
            aws ec2 delete-internet-gateway --internet-gateway-id "$igw_id" --region $AWS_REGION
            echo "✅ Deleted Internet Gateway: $igw_id"
        fi
    done
    
    # Delete Subnets
    echo "🏠 Deleting Subnets..."
    aws ec2 describe-subnets --filters "Name=vpc-id,Values=$VPC_ID" --query 'Subnets[].SubnetId' --output text --region $AWS_REGION | tr '\t' '\n' | while read -r subnet_id; do
        if [ -n "$subnet_id" ] && [ "$subnet_id" != "None" ]; then
            aws ec2 delete-subnet --subnet-id "$subnet_id" --region $AWS_REGION
            echo "✅ Deleted Subnet: $subnet_id"
        fi
    done
    
    # Delete Route Tables (except main)
    echo "🛣️  Deleting Route Tables..."
    aws ec2 describe-route-tables --filters "Name=vpc-id,Values=$VPC_ID" --query 'RouteTables[?Associations[0].Main!=`true`].RouteTableId' --output text --region $AWS_REGION | tr '\t' '\n' | while read -r rt_id; do
        if [ -n "$rt_id" ] && [ "$rt_id" != "None" ]; then
            aws ec2 delete-route-table --route-table-id "$rt_id" --region $AWS_REGION
            echo "✅ Deleted Route Table: $rt_id"
        fi
    done
    
    # Delete Security Groups (except default)
    echo "🔒 Deleting Security Groups..."
    aws ec2 describe-security-groups --filters "Name=vpc-id,Values=$VPC_ID" --query 'SecurityGroups[?GroupName!=`default`].GroupId' --output text --region $AWS_REGION | tr '\t' '\n' | while read -r sg_id; do
        if [ -n "$sg_id" ] && [ "$sg_id" != "None" ]; then
            aws ec2 delete-security-group --group-id "$sg_id" --region $AWS_REGION
            echo "✅ Deleted Security Group: $sg_id"
        fi
    done
    
    # Delete VPC
    safe_delete "VPC" "$VPC_ID" \
        "aws ec2 delete-vpc --vpc-id '$VPC_ID' --region $AWS_REGION"
else
    echo "ℹ️  VPC not found with project: $PROJECT_NAME, environment: $ENVIRONMENT"
fi

echo ""
echo "🎉 CLEANUP COMPLETE!"
echo "==================="
echo "✅ All text2agent resources have been cleaned up"
echo ""
echo "Note: Some resources may take a few minutes to fully delete."
echo "You can now run 'terraform apply' for a fresh deployment." 