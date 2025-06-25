#!/bin/bash

# Simple build script for Lambda function code only
# Dependencies will be provided by Lambda Layers

set -e  # Exit on any error

echo "Building Lambda function package (code only)..."

# Clean up previous builds
rm -f post_confirmation.zip

# Create the zip file with just the Lambda function code
cd lambda_functions/post_confirmation
zip -r ../../post_confirmation.zip index.py
cd ../..

echo "Lambda function package created: post_confirmation.zip"
echo "Package size: $(du -h post_confirmation.zip | cut -f1)"

# Verify the package contents
echo "Package contents:"
unzip -l post_confirmation.zip 