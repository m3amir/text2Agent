#!/bin/bash

# Setup S3 backend for Terraform state
# Run this script before using the S3 backend configuration

BUCKET_NAME="text2agent-terraform-state-eu-west-2"
REGION="eu-west-2"

echo "🚀 Setting up Terraform S3 backend..."

# Check if bucket already exists
if ! aws s3api head-bucket --bucket "$BUCKET_NAME" --region "$REGION" 2>/dev/null; then
    echo "📦 Creating S3 bucket: $BUCKET_NAME"
    
    # Create the bucket
    aws s3api create-bucket \
        --bucket "$BUCKET_NAME" \
        --region "$REGION" \
        --create-bucket-configuration LocationConstraint="$REGION"
    
    if [ $? -eq 0 ]; then
        echo "✅ S3 bucket created successfully"
    else
        echo "❌ Failed to create S3 bucket"
        exit 1
fi

    # Configure bucket
aws s3api put-bucket-versioning \
    --bucket "$BUCKET_NAME" \
    --versioning-configuration Status=Enabled

aws s3api put-bucket-encryption \
    --bucket "$BUCKET_NAME" \
    --server-side-encryption-configuration '{
            "Rules": [{
                "ApplyServerSideEncryptionByDefault": {
                    "SSEAlgorithm": "AES256"
                }
            }]
    }'

aws s3api put-public-access-block \
    --bucket "$BUCKET_NAME" \
    --public-access-block-configuration \
    BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true
fi

echo ""
echo "✅ Terraform S3 backend setup complete!"
echo ""
echo "Next steps:"
echo "1. Run: terraform init -migrate-state"
echo "2. Confirm migration when prompted"
echo "3. Your state will be stored in: s3://$BUCKET_NAME/text2agent/production/terraform.tfstate"
echo ""
echo "⚠️  Note: Without DynamoDB locking, avoid running multiple Terraform operations simultaneously" 