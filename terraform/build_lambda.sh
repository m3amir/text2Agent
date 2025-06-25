#!/bin/bash

# Build script for Lambda function with dependencies
# This script creates a deployment package that includes psycopg2 for PostgreSQL connectivity

set -e  # Exit on any error

echo "Building Lambda deployment package..."

# Clean up previous builds
rm -rf lambda_build
rm -f post_confirmation.zip

# Create build directory
mkdir -p lambda_build

# Copy Lambda function code
cp lambda_functions/post_confirmation/index.py lambda_build/

# Create requirements.txt for dependencies
cat > lambda_build/requirements.txt << EOF
psycopg2-binary==2.9.9
boto3>=1.26.0
EOF

echo "Installing dependencies..."

# Install dependencies to the build directory
echo "Installing psycopg2-binary..."
if command -v pip3 &> /dev/null; then
    pip3 install psycopg2-binary==2.9.9 -t lambda_build/ --no-deps
elif command -v pip &> /dev/null; then
    pip install psycopg2-binary==2.9.9 -t lambda_build/ --no-deps
else
    echo "Error: Neither pip nor pip3 found. Please install Python pip."
    exit 1
fi

# Remove unnecessary files to reduce package size
cd lambda_build
find . -type d -name "__pycache__" -exec rm -rf {} + || true
find . -name "*.pyc" -delete || true
find . -name "*.pyo" -delete || true
find . -type d -name "*.dist-info" -exec rm -rf {} + || true
find . -type d -name "*.egg-info" -exec rm -rf {} + || true

# Remove unnecessary boto3/botocore (AWS Lambda provides these)
rm -rf boto3* botocore* || true

echo "Creating deployment package..."

# Create the zip file
zip -r ../post_confirmation.zip . -x "requirements.txt"

cd ..

# Clean up build directory
rm -rf lambda_build

echo "Lambda deployment package created: post_confirmation.zip"
echo "Package size: $(du -h post_confirmation.zip | cut -f1)"

# Verify the package contents
echo "Package contents:"
unzip -l post_confirmation.zip | head -20 