#!/bin/bash

# Package Lambda function for deployment

echo "Packaging text2Agent-Post-Confirmation Lambda function..."

# Create a temporary directory for packaging
mkdir -p temp_lambda
cd temp_lambda

# Copy the function code
cp ../lambda_functions/post_confirmation/index.py .

# Install dependencies if requirements.txt exists
if [ -f ../lambda_functions/post_confirmation/requirements.txt ]; then
    echo "Installing dependencies..."
    pip install -r ../lambda_functions/post_confirmation/requirements.txt -t .
fi

# Create the zip file
echo "Creating deployment package..."
zip -r ../post_confirmation.zip .

# Clean up
cd ..
rm -rf temp_lambda

echo "Lambda package created: post_confirmation.zip"
echo "Ready for Terraform deployment!" 