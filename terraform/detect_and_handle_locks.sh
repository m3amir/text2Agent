#!/bin/bash

# ==============================================================================
# DYNAMODB-BASED LOCK DETECTION AND GITHUB ACTIONS INTEGRATION
# Detects active Terraform locks by checking DynamoDB lock table
# ==============================================================================

set -e

DYNAMODB_TABLE="text2agent-terraform-state-lock"
STATE_PATH="text2agent-terraform-state-eu-west-2/text2agent/production/terraform.tfstate"
REGION="eu-west-2"
STALE_THRESHOLD_MINUTES=30  # Consider locks older than 30 minutes as potentially stale

echo "Checking for active Terraform locks..."

# Test DynamoDB access
if ! aws dynamodb describe-table --table-name "$DYNAMODB_TABLE" --region "$REGION" >/dev/null 2>&1; then
    echo "❌ DynamoDB table not accessible"
    aws dynamodb describe-table --table-name "$DYNAMODB_TABLE" --region "$REGION" 2>&1 || true
    exit 1
fi

# Check if lock entry exists in DynamoDB
LOCK_EXISTS=false
LOCK_CONTENT=""

LOCK_ITEM=$(aws dynamodb get-item \
    --table-name "$DYNAMODB_TABLE" \
    --key "{\"LockID\":{\"S\":\"$STATE_PATH\"}}" \
    --region "$REGION" \
    --output json 2>/dev/null || echo "")

if echo "$LOCK_ITEM" | grep -q "Item"; then
    LOCK_EXISTS=true
    
    # Extract lock information from DynamoDB item
    LOCK_INFO=$(echo "$LOCK_ITEM" | jq -r '.Item.Info.S // ""' 2>/dev/null || echo "")
    
    if [ -n "$LOCK_INFO" ]; then
        LOCK_CONTENT="$LOCK_INFO"
    else
        echo "❌ Failed to read lock info from DynamoDB item"
        echo "$LOCK_ITEM"
        exit 1
    fi
else
    echo "✅ No lock entry found - all clear"
fi

# Function to calculate lock age in minutes
calculate_lock_age() {
    local created_timestamp=$1
    local current_time=$(date -u +%s)
    
    if [ "$created_timestamp" = "unknown" ] || [ -z "$created_timestamp" ]; then
        echo 999
        return
    fi
    
    local lock_time_seconds
    if command -v python3 &> /dev/null; then
        lock_time_seconds=$(python3 -c "
import sys
from datetime import datetime
try:
    created = '$created_timestamp'
    if created and created != 'unknown':
        if 'T' in created and 'Z' in created:
            dt = datetime.fromisoformat(created.replace('Z', '+00:00'))
        else:
            dt = datetime.fromisoformat(created)
        print(int(dt.timestamp()))
    else:
        print('0')
except Exception as e:
    print('0')
" 2>/dev/null)
    else
        lock_time_seconds=0
    fi
    
    if [ "$lock_time_seconds" -gt 0 ]; then
        local age_seconds=$((current_time - lock_time_seconds))
        local age_minutes=$((age_seconds / 60))
        echo $age_minutes
    else
        echo 999
    fi
}

# Function to check if a GitHub Actions workflow is still running
check_workflow_status() {
    local lock_content=$1
    local who=$(echo "$lock_content" | jq -r '.Who // ""' 2>/dev/null || echo "")
    
    if [[ "$who" =~ github-actions.*run-([0-9]+) ]] || [[ "$who" =~ runner.*([0-9]{10}) ]]; then
        local run_id="${BASH_REMATCH[1]}"
        
        if command -v gh &> /dev/null && [ -n "$GITHUB_TOKEN" ]; then
            local status=$(gh run view $run_id --json status --jq '.status' 2>/dev/null || echo "unknown")
            if [ "$status" = "in_progress" ] || [ "$status" = "queued" ]; then
                return 0  # Active workflow
            fi
        fi
    fi
    
    return 1  # Not an active workflow or can't determine
}

# Process lock if it exists
if [ "$LOCK_EXISTS" = "true" ]; then
    # Extract lock information from JSON content
    LOCK_ID=$(echo "$LOCK_CONTENT" | jq -r '.ID // "unknown"' 2>/dev/null || echo "unknown")
    OPERATION=$(echo "$LOCK_CONTENT" | jq -r '.Operation // "unknown"' 2>/dev/null || echo "unknown")
    WHO=$(echo "$LOCK_CONTENT" | jq -r '.Who // "unknown"' 2>/dev/null || echo "unknown")
    CREATED=$(echo "$LOCK_CONTENT" | jq -r '.Created // "unknown"' 2>/dev/null || echo "unknown")
    VERSION=$(echo "$LOCK_CONTENT" | jq -r '.Version // "unknown"' 2>/dev/null || echo "unknown")
    
    # Calculate lock age using created timestamp
    LOCK_AGE_MINUTES=$(calculate_lock_age "$CREATED")
    
    # Determine if lock is stale or active
    IS_STALE=false
    STALE_REASON=""
    
    # Check age threshold
    if [ "$LOCK_AGE_MINUTES" -gt "$STALE_THRESHOLD_MINUTES" ]; then
        IS_STALE=true
        STALE_REASON="Age ($LOCK_AGE_MINUTES min) exceeds threshold ($STALE_THRESHOLD_MINUTES min)"
    # Check if it's from an active GitHub Actions workflow
    elif check_workflow_status "$LOCK_CONTENT"; then
        IS_STALE=false
        STALE_REASON="Active GitHub Actions workflow detected"
    # Check for specific patterns that indicate stale locks
    elif [[ "$WHO" =~ cancelled|failed|timeout ]]; then
        IS_STALE=true
        STALE_REASON="Lock from cancelled/failed operation"
    # If we can't determine the workflow status and it's reasonably recent, be conservative
    elif [ "$LOCK_AGE_MINUTES" -lt 10 ]; then
        IS_STALE=false
        STALE_REASON="Recent lock (${LOCK_AGE_MINUTES} min) - being conservative"
    else
        IS_STALE=true
        STALE_REASON="Cannot verify active workflow for ${LOCK_AGE_MINUTES} min old lock"
    fi
    
    if [ "$IS_STALE" = "true" ]; then
        echo "❌ STALE LOCK DETECTED"
        echo "Reason: $STALE_REASON"
        
        # Export stale lock data to GitHub environment
        if [ -n "$GITHUB_ENV" ]; then
            echo "STALE_LOCKS_FOUND=true" >> $GITHUB_ENV
            echo "LOCK_COUNT=1" >> $GITHUB_ENV
            echo "LOCK_IDS=$LOCK_ID" >> $GITHUB_ENV
        fi
        
        if [ -n "$GITHUB_ENV" ]; then
            {
                echo "LOCK_DETAILS<<EOF"
                echo ""
                echo "**Stale DynamoDB Lock:**"
                echo "- **ID:** \`${LOCK_ID}\`"
                echo "- **Operation:** ${OPERATION}"
                echo "- **Created:** ${CREATED}"
                echo "- **Age:** ${LOCK_AGE_MINUTES} minutes"
                echo "- **Who:** ${WHO}"
                echo "- **Version:** ${VERSION}"
                echo "- **Reason:** ${STALE_REASON}"
                echo "EOF"
            } >> $GITHUB_ENV
        fi
        
    else
        echo "❌ ACTIVE LOCK DETECTED - WORKFLOW MUST STOP"
        echo "Status: $STALE_REASON"
        
        # Set GitHub environment to indicate active locks found
        if [ -n "$GITHUB_ENV" ]; then
            echo "ACTIVE_LOCKS_FOUND=true" >> $GITHUB_ENV
            echo "STALE_LOCKS_FOUND=false" >> $GITHUB_ENV
            
            {
                echo "ACTIVE_LOCK_DETAILS<<EOF"
                echo ""
                echo "**Active DynamoDB Lock:**"
                echo "- **ID:** \`${LOCK_ID}\`"
                echo "- **Operation:** ${OPERATION}"
                echo "- **Created:** ${CREATED}"
                echo "- **Age:** ${LOCK_AGE_MINUTES} minutes"
                echo "- **Who:** ${WHO}"
                echo "- **Version:** ${VERSION}"
                echo "- **Status:** ${STALE_REASON}"
                echo "EOF"
            } >> $GITHUB_ENV
        fi
        
        exit 1
    fi
else
    # No locks found - set GitHub environment variables for success case
    if [ -n "$GITHUB_ENV" ]; then
        echo "STALE_LOCKS_FOUND=false" >> $GITHUB_ENV
        echo "ACTIVE_LOCKS_FOUND=false" >> $GITHUB_ENV
        echo "LOCK_COUNT=0" >> $GITHUB_ENV
        echo "LOCK_IDS=" >> $GITHUB_ENV
    fi
    
    exit 0
fi 