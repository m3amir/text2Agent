#!/bin/bash

# ==============================================================================
# LOCAL TERRAFORM CONCURRENCY TEST
# Tests state locking by running concurrent terraform operations
# ==============================================================================

set -e

echo "🧪 Testing Terraform State Locking Locally"
echo "=========================================="
echo "This will test if your Terraform configuration prevents concurrent operations"
echo ""

# Function to run terraform plan with a delay
run_terraform_plan() {
    local instance=$1
    local delay=$2
    
    echo "[$instance] Starting terraform plan..."
    echo "[$instance] Timestamp: $(date)"
    
    # Run terraform plan and capture output
    if timeout 120 terraform plan -var="aws_region=eu-west-2" -var="aws_profile=" > "plan_output_${instance}.log" 2>&1; then
        echo "[$instance] ✅ Terraform plan completed successfully"
    else
        echo "[$instance] ❌ Terraform plan failed or timed out"
        echo "[$instance] Check plan_output_${instance}.log for details"
    fi
    
    echo "[$instance] End timestamp: $(date)"
}

# Function to monitor locks
monitor_locks() {
    echo "🔍 Monitoring DynamoDB locks..."
    
    for i in {1..20}; do
        echo "--- Lock Check $i ($(date)) ---"
        
        # Check for active locks
        LOCKS=$(aws dynamodb scan \
            --table-name "text2agent-terraform-state-lock" \
            --region "eu-west-2" \
            --filter-expression "attribute_exists(#info)" \
            --expression-attribute-names '{"#info": "Info"}' \
            --query 'Items[].Info.S' \
            --output text 2>/dev/null || echo "")
        
        if [ -n "$LOCKS" ]; then
            echo "🔒 Active locks detected:"
            echo "$LOCKS" | while read -r lock; do
                # Parse lock info
                LOCK_ID=$(echo "$lock" | python3 -c "
import json, sys
try:
    data = json.load(sys.stdin)
    print(f\"ID: {data.get('ID', 'unknown')[:8]}...\")
except:
    print('Parse error')
" 2>/dev/null)
                
                WHO=$(echo "$lock" | python3 -c "
import json, sys
try:
    data = json.load(sys.stdin)
    print(f\"Who: {data.get('Who', 'unknown')}\")
except:
    print('Parse error')
" 2>/dev/null)
                
                echo "  🔐 $LOCK_ID $WHO"
            done
        else
            echo "✅ No active locks"
        fi
        
        echo ""
        sleep 3
    done
}

# Check prerequisites
echo "🔧 Checking prerequisites..."

if ! command -v terraform &> /dev/null; then
    echo "❌ Terraform not found. Please install Terraform first."
    exit 1
fi

if ! aws sts get-caller-identity &> /dev/null; then
    echo "❌ AWS credentials not configured. Please configure AWS CLI first."
    exit 1
fi

if [ ! -f "backend-override.tf" ]; then
    echo "❌ Backend configuration not found. Running setup script..."
    chmod +x ./setup_terraform_backend.sh
    ./setup_terraform_backend.sh
fi

echo "✅ Prerequisites check passed"
echo ""

# Initialize terraform
echo "🚀 Initializing Terraform..."
terraform init -reconfigure
echo ""

# Clean up any existing log files
rm -f plan_output_*.log

echo "🧪 Starting Concurrency Test"
echo "============================"
echo "This test will:"
echo "1. Start monitoring DynamoDB locks in background"
echo "2. Run two terraform plan operations simultaneously"
echo "3. Show you the locking behavior"
echo ""

# Start lock monitoring in background
monitor_locks > lock_monitor.log 2>&1 &
MONITOR_PID=$!

# Give monitor a moment to start
sleep 2

echo "📋 Test Results will show:"
echo "- First operation should acquire lock immediately"
echo "- Second operation should wait with message: 'Acquiring state lock...'"
echo ""

# Run two terraform plans simultaneously
echo "🏁 Starting concurrent terraform plans..."
run_terraform_plan "PLAN-1" 0 &
PID1=$!

# Small delay to let first one start
sleep 2

run_terraform_plan "PLAN-2" 5 &
PID2=$!

# Wait for both to complete
echo "⏳ Waiting for operations to complete..."
wait $PID1
wait $PID2

# Stop monitoring
kill $MONITOR_PID 2>/dev/null || true

echo ""
echo "📊 Test Results"
echo "==============="

echo ""
echo "🔍 Lock Monitor Output:"
echo "------------------------"
tail -20 lock_monitor.log

echo ""
echo "📁 Plan Output Files Created:"
echo "- plan_output_PLAN-1.log"
echo "- plan_output_PLAN-2.log"
echo "- lock_monitor.log"
echo ""

echo "🧪 Concurrency Test Complete!"
echo ""
echo "Expected Behavior:"
echo "✅ First plan should run immediately"
echo "⏳ Second plan should show 'Acquiring state lock...'"
echo "🔒 Lock monitor should show active locks during execution"
echo ""
echo "If you see lock acquisition messages, your state locking is working correctly! 🎯" 