#!/bin/bash

# Build psycopg2 Lambda Layer using Docker for Linux compatibility
# This ensures the layer works properly in AWS Lambda environment

set -e  # Exit on any error

echo "Building psycopg2 Lambda Layer..."

# Clean up previous builds
rm -rf layer_build 2>/dev/null || true
rm -f psycopg2-layer.zip

# Create layer directory structure
mkdir -p layer_build/python

echo "Installing psycopg2-binary for Lambda..."

# Check if Docker is available
if command -v docker &> /dev/null; then
    echo "Using Docker to build Linux-compatible layer..."
    
    # Get current user ID and group ID for proper permissions
    USER_ID=$(id -u)
    GROUP_ID=$(id -g)
    
    # Use Amazon Linux container to build the layer with proper user mapping
    docker run --rm \
        -v "$PWD/layer_build/python:/var/task" \
        -u "$USER_ID:$GROUP_ID" \
        amazonlinux:2 bash -c "
            yum update -y && \
            yum install -y python3 python3-pip && \
            pip3 install psycopg2-binary==2.9.9 -t /var/task/
        " || {
        # Fallback: run as root and fix permissions afterward
        echo "Running as root and fixing permissions..."
        docker run --rm \
            -v "$PWD/layer_build/python:/var/task" \
            amazonlinux:2 bash -c "
                yum update -y && \
                yum install -y python3 python3-pip && \
                pip3 install psycopg2-binary==2.9.9 -t /var/task/ && \
                chmod -R 755 /var/task && \
                chown -R $USER_ID:$GROUP_ID /var/task || true
            "
    }
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
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find . -name "*.pyc" -delete 2>/dev/null || true
find . -name "*.pyo" -delete 2>/dev/null || true
find . -type d -name "*.dist-info" -exec rm -rf {} + 2>/dev/null || true
find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true

echo "Creating layer zip file..."

# Create the layer zip file
cd ..
zip -r ../psycopg2-layer.zip python/
cd ..

# Clean up build directory
echo "Cleaning up build directory..."
rm -rf layer_build 2>/dev/null || true

echo "psycopg2 Lambda Layer created: psycopg2-layer.zip"
echo "Layer size: $(du -h psycopg2-layer.zip | cut -f1)"

# Verify the layer contents
echo "Layer contents:"
unzip -l psycopg2-layer.zip | head -20 