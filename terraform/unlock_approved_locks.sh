#!/bin/bash

# ==============================================================================
# DYNAMODB LOCK REMOVAL SCRIPT
# Removes approved stale lock entries from DynamoDB table
# ==============================================================================

set -e

DYNAMODB_TABLE="text2agent-terraform-state-lock"
STATE_PATH="text2agent-terraform-state-eu-west-2/text2agent/production/terraform.tfstate"
REGION="eu-west-2"

echo "Removing approved DynamoDB lock entries..."

# Check if environment variables are set
if [ -z "$LOCK_IDS" ]; then
    echo "❌ No LOCK_IDS environment variable found"
    exit 1
fi

# Verify AWS access
aws sts get-caller-identity >/dev/null || {
    echo "❌ AWS credentials not available"
    exit 1
}

# Check if DynamoDB table exists
if ! aws dynamodb describe-table --table-name "$DYNAMODB_TABLE" --region "$REGION" >/dev/null 2>&1; then
    echo "❌ Cannot access DynamoDB table"
    exit 1
fi

# Check if lock entry exists
LOCK_ITEM=$(aws dynamodb get-item \
    --table-name "$DYNAMODB_TABLE" \
    --key "{\"LockID\":{\"S\":\"$STATE_PATH\"}}" \
    --region "$REGION" \
    --output json 2>/dev/null || echo "")

if echo "$LOCK_ITEM" | grep -q "Item"; then
    # Extract lock information from DynamoDB item
    LOCK_INFO=$(echo "$LOCK_ITEM" | jq -r '.Item.Info.S // ""' 2>/dev/null || echo "")
    
    if [ -n "$LOCK_INFO" ]; then
        CURRENT_LOCK_ID=$(echo "$LOCK_INFO" | jq -r '.ID // "unknown"' 2>/dev/null || echo "unknown")
        
        # Check if the current lock ID matches what we're supposed to remove
        if [[ "$LOCK_IDS" == *"$CURRENT_LOCK_ID"* ]]; then
            # Remove the lock entry from DynamoDB
            if aws dynamodb delete-item \
                --table-name "$DYNAMODB_TABLE" \
                --key "{\"LockID\":{\"S\":\"$STATE_PATH\"}}" \
                --region "$REGION" >/dev/null 2>&1; then
                
                # Verify removal
                VERIFY_ITEM=$(aws dynamodb get-item \
                    --table-name "$DYNAMODB_TABLE" \
                    --key "{\"LockID\":{\"S\":\"$STATE_PATH\"}}" \
                    --region "$REGION" \
                    --output json 2>/dev/null || echo "")
                
                if echo "$VERIFY_ITEM" | grep -q "Item"; then
                    echo "❌ Lock entry still exists after deletion attempt"
                    exit 1
                else
                    echo "✅ Lock entry successfully removed"
                fi
            else
                echo "❌ Failed to remove lock entry from DynamoDB"
                exit 1
            fi
        else
            echo "❌ Lock ID mismatch - manual review needed"
            exit 1
        fi
    else
        echo "❌ Could not read lock info from DynamoDB item"
        exit 1
    fi
else
    echo "✅ No lock entry found - already removed or never existed"
fi 