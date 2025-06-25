#!/bin/bash

# Build script for Lambda function WITHOUT psycopg2 dependencies
# psycopg2 is provided via Lambda Layer to ensure Linux compatibility

set -e  # Exit on any error

echo "Building Lambda deployment package (without psycopg2)..."

# Clean up previous builds
rm -rf lambda_build
rm -f post_confirmation.zip

# Create build directory
mkdir -p lambda_build

# Copy Lambda function code
cp lambda_functions/post_confirmation/index.py lambda_build/

echo "Creating deployment package (function code only)..."

# Create the zip file with just the function code
cd lambda_build
zip -r ../post_confirmation.zip . 

cd ..

# Clean up build directory
rm -rf lambda_build

echo "Lambda deployment package created: post_confirmation.zip"
echo "Package size: $(du -h post_confirmation.zip | cut -f1)"

# Verify the package contents
echo "Package contents:"
unzip -l post_confirmation.zip

echo ""
echo "Note: psycopg2 dependency is provided by the Lambda Layer for Linux compatibility." 