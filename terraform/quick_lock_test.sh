#!/bin/bash

# ==============================================================================
# QUICK TERRAFORM LOCK TEST
# Tests if DynamoDB state locking is actually preventing concurrent operations
# ==============================================================================

echo "🧪 Quick Terraform Lock Test"
echo "============================"
echo "This will verify that state locking is working properly"
echo ""

# Check if terraform is initialized
if [ ! -d ".terraform" ]; then
    echo "🔧 Initializing Terraform..."
    terraform init -reconfigure
fi

echo "🔍 Testing lock acquisition..."
echo "This test will:"
echo "1. Start a terraform plan that takes time"
echo "2. Immediately try a second terraform plan" 
echo "3. Show you if the second one waits for the lock"
echo ""

# Clean up any existing locks first
echo "🧹 Checking for existing locks..."
EXISTING_LOCKS=$(aws dynamodb scan \
    --table-name "text2agent-terraform-state-lock" \
    --region "eu-west-2" \
    --filter-expression "attribute_exists(#info)" \
    --expression-attribute-names '{"#info": "Info"}' \
    --query 'Items[].Info.S' \
    --output text 2>/dev/null || echo "")

if [ -n "$EXISTING_LOCKS" ]; then
    echo "⚠️ Found existing locks - this test may not work properly"
    echo "Run './cleanup_stale_locks.sh' first to clear them"
    exit 1
fi

echo "✅ No existing locks found"
echo ""

# Function to run terraform with lock testing
test_terraform_lock() {
    local test_name=$1
    local delay_before=$2
    
    echo "[$test_name] Starting in ${delay_before}s..."
    sleep $delay_before
    
    echo "[$test_name] Running terraform plan..."
    echo "[$test_name] Timestamp: $(date)"
    
    # This should show lock acquisition behavior
    terraform plan -var="aws_region=eu-west-2" -var="aws_profile=" > "${test_name}_output.log" 2>&1
    local exit_code=$?
    
    echo "[$test_name] Completed with exit code: $exit_code"
    echo "[$test_name] End timestamp: $(date)"
    
    # Check if lock acquisition was mentioned
    if grep -q "Acquiring state lock" "${test_name}_output.log"; then
        echo "[$test_name] ✅ LOCK ACQUISITION DETECTED - State locking is working!"
    else
        echo "[$test_name] ⚠️ No lock acquisition message found"
    fi
}

echo "🏁 Starting concurrent test..."
echo "Watch for 'Acquiring state lock' messages..."
echo ""

# Start first terraform plan
test_terraform_lock "TEST-A" 0 &
PID_A=$!

# Start second terraform plan immediately  
test_terraform_lock "TEST-B" 2 &
PID_B=$!

# Wait for both to complete
echo "⏳ Waiting for both tests to complete..."
wait $PID_A
wait $PID_B

echo ""
echo "📊 Results Analysis"
echo "=================="

echo ""
echo "📁 Output files created:"
echo "- TEST-A_output.log"
echo "- TEST-B_output.log"
echo ""

echo "🔍 Checking for lock acquisition messages..."
echo ""

if grep -q "Acquiring state lock" TEST-A_output.log; then
    echo "TEST-A: ✅ Lock acquisition detected"
else
    echo "TEST-A: ❌ No lock acquisition message"
fi

if grep -q "Acquiring state lock" TEST-B_output.log; then
    echo "TEST-B: ✅ Lock acquisition detected" 
else
    echo "TEST-B: ❌ No lock acquisition message"
fi

echo ""
echo "📋 Expected Result:"
echo "- At least ONE test should show 'Acquiring state lock'"
echo "- This proves the second operation waited for the first"
echo ""

echo "🎯 If you see lock acquisition messages, DynamoDB locking is working!"
echo "🚨 If you see NO lock messages, there's a configuration issue." 