#!/bin/bash

# Build psycopg2 Lambda Layer using Docker for Linux compatibility
# This ensures the layer works properly in AWS Lambda environment

set -e  # Exit on any error

echo "Building psycopg2 Lambda Layer..."

# Clean up previous builds
rm -rf layer_build 2>/dev/null || true
rm -f psycopg2-layer.zip

# Create layer directory structure
mkdir -p layer_build

echo "Installing psycopg2-binary for Lambda..."

# Check if Docker is available
if command -v docker &> /dev/null; then
    echo "Using Docker to build Linux-compatible layer for Python 3.11..."
    
    # Use AWS SAM build image for Python 3.11 (matches Lambda runtime)
    docker run --rm \
        -v "$PWD/layer_build:/var/task" \
        public.ecr.aws/sam/build-python3.11:latest \
        /bin/sh -c "pip install psycopg2-binary==2.9.9 -t /var/task/python/lib/python3.11/site-packages/"
        
    echo "✅ psycopg2 installed in Python 3.11 site-packages"
else
    echo "❌ ERROR: Docker not available. Docker is required for building Linux-compatible layers."
    echo "Please install Docker and try again."
    exit 1
fi

# Clean up unnecessary files to reduce layer size
echo "Cleaning up unnecessary files..."
cd layer_build
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find . -name "*.pyc" -delete 2>/dev/null || true
find . -name "*.pyo" -delete 2>/dev/null || true
find . -type d -name "*.dist-info" -exec rm -rf {} + 2>/dev/null || true
find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true

echo "Creating layer zip file..."

# Create the layer zip file (Lambda layers expect python/ directory in root)
zip -r ../psycopg2-layer.zip python/
cd ..

# Clean up build directory
echo "Cleaning up build directory..."
rm -rf layer_build 2>/dev/null || true

echo "✅ psycopg2 Lambda Layer created: psycopg2-layer.zip"
echo "📏 Layer size: $(du -h psycopg2-layer.zip | cut -f1)"

# Verify the layer contents
echo "📋 Layer contents:"
unzip -l psycopg2-layer.zip | head -20

echo ""
echo "🐍 This layer is built for Python 3.11 runtime"
echo "📦 Layer structure: python/lib/python3.11/site-packages/"
echo "✅ Ready for deployment to AWS Lambda!" 