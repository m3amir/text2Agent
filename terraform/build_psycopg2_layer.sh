#!/bin/bash

# Build psycopg2 Lambda Layer using Docker for Linux compatibility
# This ensures the layer works properly in AWS Lambda environment

set -e  # Exit on any error

echo "Building psycopg2 Lambda Layer..."

# Clean up previous builds
rm -rf layer_build
rm -f psycopg2-layer.zip

# Create layer directory structure
mkdir -p layer_build/python

echo "Installing psycopg2-binary for Lambda..."

# Check if Docker is available
if command -v docker &> /dev/null; then
    echo "Using Docker to build Linux-compatible layer..."
    
    # Use Amazon Linux container to build the layer
    docker run --rm -v "$PWD/layer_build/python:/var/task" amazonlinux:2 bash -c "
        yum update -y && \
        yum install -y python3 python3-pip && \
        pip3 install psycopg2-binary==2.9.9 -t /var/task/
    "
else
    echo "Docker not available, trying local installation..."
    echo "Note: This may not work in AWS Lambda if you're not on Linux"
    
    # Fallback to local installation
    if command -v pip3 &> /dev/null; then
        pip3 install psycopg2-binary==2.9.9 -t layer_build/python/
    elif command -v pip &> /dev/null; then
        pip install psycopg2-binary==2.9.9 -t layer_build/python/
    else
        echo "Error: Neither pip nor pip3 found."
        exit 1
    fi
fi

# Clean up unnecessary files to reduce layer size
cd layer_build/python
find . -type d -name "__pycache__" -exec rm -rf {} + || true
find . -name "*.pyc" -delete || true
find . -name "*.pyo" -delete || true
find . -type d -name "*.dist-info" -exec rm -rf {} + || true
find . -type d -name "*.egg-info" -exec rm -rf {} + || true

echo "Creating layer zip file..."

# Create the layer zip file
cd ..
zip -r ../psycopg2-layer.zip python/
cd ..

# Clean up build directory
rm -rf layer_build

echo "psycopg2 Lambda Layer created: psycopg2-layer.zip"
echo "Layer size: $(du -h psycopg2-layer.zip | cut -f1)"

# Verify the layer contents
echo "Layer contents:"
unzip -l psycopg2-layer.zip | head -20 