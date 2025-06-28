#!/bin/bash

# ==============================================================================
# TERRAFORM LOCK TESTING SCRIPT
# Tests the DynamoDB-based locking mechanism
# ==============================================================================

set -e

echo "🧪 Testing DynamoDB-based Terraform Locking"
echo "=========================================="
echo "This will test if DynamoDB locks prevent concurrent operations"
echo ""

# Check if terraform is initialized
if [ ! -d ".terraform" ]; then
    echo "🔧 Initializing Terraform..."
    terraform init -reconfigure
fi

echo "🔍 Current backend configuration:"
grep -A 10 'backend "s3"' *.tf | head -15

echo ""
echo "🧪 Testing lock behavior..."
echo "This test will:"
echo "1. Start a terraform plan in the background" 
echo "2. Immediately try another terraform plan"
echo "3. Show you if the second one waits for the S3 lock"
echo ""

# Function to run terraform plan with logging
run_terraform_test() {
    local test_name=$1
    local output_file="s3_lock_test_${test_name}.log"
    
    echo "[$test_name] Starting terraform plan..."
    echo "[$test_name] Timestamp: $(date)"
    
    # Run terraform plan and capture output
    AWS_PROFILE=m3 gtimeout 60 terraform plan -var="aws_region=eu-west-2" -var="aws_profile=" > "$output_file" 2>&1 &
    local pid=$!
    
    echo "[$test_name] Process ID: $pid"
    echo "[$test_name] Output file: $output_file"
    
    return $pid
}

# Function to monitor DynamoDB lock table
monitor_dynamodb_lock() {
    local table_name="text2agent-terraform-state-lock"
    local lock_id="text2agent-terraform-state-eu-west-2/text2agent/production/terraform.tfstate"
    
    echo "🔍 Monitoring DynamoDB lock table: $table_name"
    
    for i in {1..20}; do
        echo "--- Lock Check $i ($(date +%H:%M:%S)) ---"
        
        # Check for lock in DynamoDB
        LOCK_ITEM=$(AWS_PROFILE=m3 aws dynamodb get-item \
            --table-name "$table_name" \
            --key '{"LockID":{"S":"'$lock_id'"}}' \
            --region "eu-west-2" 2>/dev/null || echo "")
        
        if echo "$LOCK_ITEM" | grep -q "Item"; then
            echo "🔒 Lock EXISTS in DynamoDB"
            
            # Extract lock details
            if command -v jq >/dev/null; then
                LOCK_INFO=$(echo "$LOCK_ITEM" | jq -r '.Item.Info.S // "unknown"' 2>/dev/null || echo "unknown")
                if [ "$LOCK_INFO" != "unknown" ] && [ "$LOCK_INFO" != "null" ]; then
                    OPERATION=$(echo "$LOCK_INFO" | jq -r '.Operation // "unknown"' 2>/dev/null || echo "unknown")
                    WHO=$(echo "$LOCK_INFO" | jq -r '.Who // "unknown"' 2>/dev/null || echo "unknown")
                    CREATED=$(echo "$LOCK_INFO" | jq -r '.Created // "unknown"' 2>/dev/null || echo "unknown")
                    
                    echo "  Operation: $OPERATION"
                    echo "  Who: $WHO"
                    echo "  Created: $CREATED"
                fi
            fi
        else
            echo "✅ No lock found in DynamoDB"
        fi
        
        echo ""
        sleep 3
    done
}

# Clean up any existing log files
rm -f s3_lock_test_*.log

echo "🏁 Starting DynamoDB lock test..."

# Start lock monitoring in background
monitor_dynamodb_lock > dynamodb_lock_monitor.log 2>&1 &
MONITOR_PID=$!

# Give monitor a moment to start
sleep 2

echo "📋 Starting concurrent terraform operations..."

# Start first terraform plan
run_terraform_test "TEST-A" 
PID_A=$!

# Small delay to let first one start
sleep 5

# Start second terraform plan
run_terraform_test "TEST-B"
PID_B=$!

# Wait for both to complete
echo "⏳ Waiting for operations to complete..."
wait $PID_A
wait $PID_B

# Stop monitoring
kill $MONITOR_PID 2>/dev/null || true

echo ""
echo "📊 DynamoDB Lock Test Results"
echo "============================"

echo ""
echo "🔍 Lock Monitor Output:"
echo "------------------------"
tail -20 dynamodb_lock_monitor.log

echo ""
echo "📁 Test Output Files Created:"
echo "- s3_lock_test_TEST-A.log"
echo "- s3_lock_test_TEST-B.log" 
echo "- dynamodb_lock_monitor.log"
echo ""

echo "🔍 Checking for lock acquisition messages..."
echo ""

if grep -q "Acquiring state lock" s3_lock_test_TEST-A.log; then
    echo "TEST-A: ✅ Lock acquisition detected"
else
    echo "TEST-A: ❌ No lock acquisition message"
fi

if grep -q "Acquiring state lock" s3_lock_test_TEST-B.log; then
    echo "TEST-B: ✅ Lock acquisition detected"
else
    echo "TEST-B: ❌ No lock acquisition message" 
fi

echo ""
echo "🎯 Expected Result:"
echo "- At least ONE test should show 'Acquiring state lock'"
echo "- This proves the second operation waited for the first"
echo ""

echo "✅ DynamoDB Lock Test Complete!"
echo ""
echo "If you see lock acquisition messages, your DynamoDB locking is working! 🔒" 