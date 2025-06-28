#!/bin/bash

# ==============================================================================
# IMPROVED STALE LOCK DETECTION AND GITHUB ACTIONS INTEGRATION
# Properly distinguishes between stale and active locks
# ==============================================================================

set -e

TABLE_NAME="text2agent-terraform-state-lock"
REGION="eu-west-2"
STALE_THRESHOLD_MINUTES=30  # Consider locks older than 30 minutes as potentially stale

echo "🔍 Checking for stale Terraform state locks..."
echo "=============================================="

# Function to check if a GitHub Actions workflow is still running
check_workflow_status() {
    local who=$1
    local created=$2
    
    # Extract workflow run ID from the "Who" field if it contains GitHub Actions info
    if [[ "$who" =~ github-actions.*run-([0-9]+) ]]; then
        local run_id="${BASH_REMATCH[1]}"
        echo "🔍 Checking GitHub Actions run $run_id status..."
        
        # Check if workflow is still running (requires GitHub CLI or API)
        if command -v gh &> /dev/null; then
            local status=$(gh run view $run_id --json status --jq '.status' 2>/dev/null || echo "unknown")
            echo "   Status: $status"
            if [ "$status" = "in_progress" ] || [ "$status" = "queued" ]; then
                return 0  # Active workflow
            fi
        fi
    fi
    
    return 1  # Not an active workflow or can't determine
}

# Function to calculate lock age in minutes
calculate_lock_age() {
    local created=$1
    local current_time=$(date -u +%s)
    
    # Parse the created timestamp
    local created_seconds
    if command -v python3 &> /dev/null; then
        created_seconds=$(python3 -c "
import sys
from datetime import datetime
try:
    created = '$created'
    if created and created != 'Unknown':
        if 'T' in created:
            # ISO format
            dt = datetime.fromisoformat(created.replace('Z', '+00:00'))
        else:
            # Try parsing as UTC format
            dt = datetime.strptime(created, '%Y-%m-%d %H:%M:%S UTC')
        print(int(dt.timestamp()))
    else:
        print('0')
except Exception as e:
    print('0')
" 2>/dev/null)
    else
        created_seconds=0
    fi
    
    if [ "$created_seconds" -gt 0 ]; then
        local age_seconds=$((current_time - created_seconds))
        local age_minutes=$((age_seconds / 60))
        echo $age_minutes
    else
        echo 999  # Unknown age, treat as very old
    fi
}

# Check if any locks exist
LOCKS=$(aws dynamodb scan \
    --table-name "$TABLE_NAME" \
    --region "$REGION" \
    --filter-expression "attribute_exists(#info)" \
    --expression-attribute-names '{"#info": "Info"}' \
    --query 'Items[].Info.S' \
    --output text 2>/dev/null || echo "")

if [ -z "$LOCKS" ]; then
    echo "✅ No locks found - all clear!"
    echo "STALE_LOCKS_FOUND=false" >> $GITHUB_ENV
    exit 0
fi

echo "🔍 Found locks - analyzing for staleness..."

# Process lock information
TEMP_DIR=$(mktemp -d)
STALE_LOCK_DETAILS_FILE="$TEMP_DIR/stale_lock_details"
ACTIVE_LOCK_DETAILS_FILE="$TEMP_DIR/active_lock_details"
STALE_LOCK_IDS_FILE="$TEMP_DIR/stale_lock_ids"

STALE_LOCK_COUNT=0
ACTIVE_LOCK_COUNT=0
> "$STALE_LOCK_DETAILS_FILE"
> "$ACTIVE_LOCK_DETAILS_FILE"
> "$STALE_LOCK_IDS_FILE"

# Process each lock
while IFS= read -r lock_json; do
    if [ -n "$lock_json" ]; then
        # Extract lock information
        LOCK_ID=$(echo "$lock_json" | python3 -c "
import json, sys
try:
    data = json.load(sys.stdin)
    print(data.get('ID', 'unknown'))
except:
    print('unknown')
" 2>/dev/null)
        
        OPERATION=$(echo "$lock_json" | python3 -c "
import json, sys
try:
    data = json.load(sys.stdin)
    print(data.get('Operation', 'unknown'))
except:
    print('unknown')
" 2>/dev/null)
        
        WHO=$(echo "$lock_json" | python3 -c "
import json, sys
try:
    data = json.load(sys.stdin)
    print(data.get('Who', 'unknown'))
except:
    print('unknown')
" 2>/dev/null)
        
        CREATED=$(echo "$lock_json" | python3 -c "
import json, sys
from datetime import datetime
try:
    data = json.load(sys.stdin)
    created = data.get('Created', '')
    if created:
        dt = datetime.fromisoformat(created.replace('Z', '+00:00'))
        print(dt.strftime('%Y-%m-%d %H:%M:%S UTC'))
    else:
        print('Unknown')
except:
    print('Parse error')
" 2>/dev/null)
        
        # Calculate lock age
        LOCK_AGE_MINUTES=$(calculate_lock_age "$CREATED")
        
        echo ""
        echo "🔍 Analyzing lock: ${LOCK_ID:0:8}..."
        echo "   Created: $CREATED"
        echo "   Age: $LOCK_AGE_MINUTES minutes"
        echo "   Who: $WHO"
        echo "   Operation: $OPERATION"
        
        # Determine if lock is stale or active
        IS_STALE=false
        STALE_REASON=""
        
        # Check age threshold
        if [ "$LOCK_AGE_MINUTES" -gt "$STALE_THRESHOLD_MINUTES" ]; then
            IS_STALE=true
            STALE_REASON="Age ($LOCK_AGE_MINUTES min) exceeds threshold ($STALE_THRESHOLD_MINUTES min)"
        # Check if it's from a completed/failed GitHub Actions workflow
        elif check_workflow_status "$WHO" "$CREATED"; then
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
            echo "   🚨 STALE: $STALE_REASON"
            STALE_LOCK_COUNT=$((STALE_LOCK_COUNT + 1))
            
            # Add to stale locks
            cat >> "$STALE_LOCK_DETAILS_FILE" << EOF

**Stale Lock ${STALE_LOCK_COUNT}:**
- **ID:** \`${LOCK_ID}\`
- **Operation:** ${OPERATION}
- **Created:** ${CREATED}
- **Age:** ${LOCK_AGE_MINUTES} minutes
- **Who:** ${WHO}
- **Reason:** ${STALE_REASON}
EOF
            
            # Append to stale lock IDs file
            if [ -s "$STALE_LOCK_IDS_FILE" ]; then
                echo -n "," >> "$STALE_LOCK_IDS_FILE"
            fi
            echo -n "$LOCK_ID" >> "$STALE_LOCK_IDS_FILE"
        else
            echo "   ✅ ACTIVE: $STALE_REASON"
            ACTIVE_LOCK_COUNT=$((ACTIVE_LOCK_COUNT + 1))
            
            # Add to active locks
            cat >> "$ACTIVE_LOCK_DETAILS_FILE" << EOF

**Active Lock ${ACTIVE_LOCK_COUNT}:**
- **ID:** \`${LOCK_ID}\`
- **Operation:** ${OPERATION}
- **Created:** ${CREATED}
- **Age:** ${LOCK_AGE_MINUTES} minutes
- **Who:** ${WHO}
- **Status:** ${STALE_REASON}
EOF
        fi
    fi
done <<< "$LOCKS"

# Read the accumulated data
STALE_LOCK_DETAILS=$(cat "$STALE_LOCK_DETAILS_FILE")
ACTIVE_LOCK_DETAILS=$(cat "$ACTIVE_LOCK_DETAILS_FILE")
STALE_LOCK_IDS=$(cat "$STALE_LOCK_IDS_FILE")

echo ""
echo "📊 Lock Analysis Summary:"
echo "   Total locks found: $((STALE_LOCK_COUNT + ACTIVE_LOCK_COUNT))"
echo "   Stale locks: $STALE_LOCK_COUNT"
echo "   Active locks: $ACTIVE_LOCK_COUNT"

# Handle active locks
if [ "$ACTIVE_LOCK_COUNT" -gt 0 ]; then
    echo ""
    echo "🚨 ACTIVE LOCKS DETECTED - WORKFLOW MUST WAIT"
    echo "=============================================="
    echo "Found $ACTIVE_LOCK_COUNT active lock(s) from ongoing operations."
    echo "This workflow will be blocked until the active operations complete."
    echo ""
    echo "Active lock details:"
    echo "$ACTIVE_LOCK_DETAILS"
    echo ""
    echo "❌ Exiting to prevent interference with active Terraform operations."
    echo "   This workflow will need to be re-run after the active operations complete."
    
    # Set GitHub environment to indicate active locks found
    echo "ACTIVE_LOCKS_FOUND=true" >> $GITHUB_ENV
    echo "STALE_LOCKS_FOUND=false" >> $GITHUB_ENV
    {
        echo "ACTIVE_LOCK_DETAILS<<EOF"
        echo "$ACTIVE_LOCK_DETAILS"
        echo "EOF"
    } >> $GITHUB_ENV
    
    exit 1  # Exit with error to stop the workflow
fi

# Handle stale locks
if [ "$STALE_LOCK_COUNT" -gt 0 ]; then
    echo ""
    echo "🔧 STALE LOCKS DETECTED - APPROVAL REQUIRED"
    echo "=========================================="
    echo "Found $STALE_LOCK_COUNT stale lock(s) that need to be removed."
    
    # Export stale lock data to GitHub environment
    echo "STALE_LOCKS_FOUND=true" >> $GITHUB_ENV
    {
        echo "LOCK_DETAILS<<EOF"
        echo "$STALE_LOCK_DETAILS"
        echo "EOF"
    } >> $GITHUB_ENV
    echo "LOCK_IDS=$STALE_LOCK_IDS" >> $GITHUB_ENV
    echo "LOCK_COUNT=$STALE_LOCK_COUNT" >> $GITHUB_ENV
    
    echo ""
    echo "🔄 Workflow will now pause for manual approval to remove stale locks..."
else
    echo ""
    echo "✅ No stale locks detected - proceeding with Terraform operations"
    echo "STALE_LOCKS_FOUND=false" >> $GITHUB_ENV
fi

# Cleanup
rm -rf "$TEMP_DIR" 