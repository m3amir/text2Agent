#!/bin/bash

# ==============================================================================
# DYNAMODB LOCK REMOVAL SCRIPT
# Removes approved stale lock entries from DynamoDB table
# ==============================================================================

set -e

DYNAMODB_TABLE="text2agent-terraform-state-lock"
STATE_PATH="text2agent-terraform-state-eu-west-2/text2agent/production/terraform.tfstate"
REGION="eu-west-2"

echo "🔓 Removing Approved DynamoDB Lock Entries"
echo "========================================="

# Check if environment variables are set
if [ -z "$LOCK_IDS" ]; then
    echo "❌ No LOCK_IDS environment variable found"
    echo "This script should only be run after approval in GitHub Actions"
    exit 1
fi

echo "📋 Lock Details:"
echo "   DynamoDB Table: $DYNAMODB_TABLE"
echo "   State Path: $STATE_PATH"
echo "   Region: $REGION"
echo "   Lock IDs to remove: $LOCK_IDS"
echo ""

# Verify AWS access
echo "🔧 Verifying AWS access..."
aws sts get-caller-identity || {
    echo "❌ AWS credentials not available"
    exit 1
}

# Check if DynamoDB table exists
echo "🔍 Verifying DynamoDB table access..."
if aws dynamodb describe-table --table-name "$DYNAMODB_TABLE" --region "$REGION" >/dev/null 2>&1; then
    echo "   ✅ DynamoDB table accessible"
else
    echo "   ❌ Cannot access DynamoDB table"
    exit 1
fi

# Check if lock entry exists
echo "🔍 Checking if lock entry exists..."
LOCK_ITEM=$(aws dynamodb get-item \
    --table-name "$DYNAMODB_TABLE" \
    --key "{\"LockID\":{\"S\":\"$STATE_PATH\"}}" \
    --region "$REGION" \
    --output json 2>/dev/null || echo "")

if echo "$LOCK_ITEM" | grep -q "Item"; then
    echo "   ✅ Lock entry found in DynamoDB"
    
    # Extract lock information from DynamoDB item
    LOCK_INFO=$(echo "$LOCK_ITEM" | jq -r '.Item.Info.S // ""' 2>/dev/null || echo "")
    
    if [ -n "$LOCK_INFO" ]; then
        echo "🔍 Verifying lock content..."
        CURRENT_LOCK_ID=$(echo "$LOCK_INFO" | jq -r '.ID // "unknown"' 2>/dev/null || echo "unknown")
        OPERATION=$(echo "$LOCK_INFO" | jq -r '.Operation // "unknown"' 2>/dev/null || echo "unknown")
        WHO=$(echo "$LOCK_INFO" | jq -r '.Who // "unknown"' 2>/dev/null || echo "unknown")
        CREATED=$(echo "$LOCK_INFO" | jq -r '.Created // "unknown"' 2>/dev/null || echo "unknown")
        
        echo "   Current lock ID: $CURRENT_LOCK_ID"
        echo "   Operation: $OPERATION"
        echo "   Who: $WHO"
        echo "   Created: $CREATED"
        
        # Check if the current lock ID matches what we're supposed to remove
        if [[ "$LOCK_IDS" == *"$CURRENT_LOCK_ID"* ]]; then
            echo "   ✅ Lock ID matches approval - safe to remove"
            
            # Remove the lock entry from DynamoDB
            echo "🔓 Removing lock entry from DynamoDB..."
            if aws dynamodb delete-item \
                --table-name "$DYNAMODB_TABLE" \
                --key "{\"LockID\":{\"S\":\"$STATE_PATH\"}}" \
                --region "$REGION" >/dev/null 2>&1; then
                echo "   ✅ Lock entry successfully removed!"
                
                # Verify removal
                echo "🔍 Verifying lock removal..."
                VERIFY_ITEM=$(aws dynamodb get-item \
                    --table-name "$DYNAMODB_TABLE" \
                    --key "{\"LockID\":{\"S\":\"$STATE_PATH\"}}" \
                    --region "$REGION" \
                    --output json 2>/dev/null || echo "")
                
                if echo "$VERIFY_ITEM" | grep -q "Item"; then
                    echo "   ⚠️ Warning: Lock entry still exists after deletion attempt"
                    exit 1
                else
                    echo "   ✅ Confirmed: Lock entry successfully removed"
                fi
            else
                echo "   ❌ Failed to remove lock entry from DynamoDB"
                echo "   Error details:"
                aws dynamodb delete-item \
                    --table-name "$DYNAMODB_TABLE" \
                    --key "{\"LockID\":{\"S\":\"$STATE_PATH\"}}" \
                    --region "$REGION" 2>&1 || true
                exit 1
            fi
        else
            echo "   ⚠️ Lock ID mismatch!"
            echo "   Expected: $LOCK_IDS"
            echo "   Current: $CURRENT_LOCK_ID"
            echo "   The lock may have changed since approval - manual review needed"
            exit 1
        fi
    else
        echo "   ❌ Could not read lock info from DynamoDB item"
        echo "   Raw item:"
        echo "$LOCK_ITEM"
        exit 1
    fi
else
    echo "   ℹ️ No lock entry found - already removed or never existed"
    echo "   This is normal if the lock was already released"
fi

echo ""
echo "🎯 Lock Removal Summary:"
echo "   ✅ Approved stale locks have been removed from DynamoDB"
echo "   ✅ Terraform operations can now proceed"
echo ""
echo "📊 Next Steps:"
echo "   - The workflow will continue with terraform operations"
echo "   - Future operations will create new locks as needed"
echo "   - Monitor subsequent jobs for successful completion" 