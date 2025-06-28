#!/bin/bash

# ==============================================================================
# STALE LOCK DETECTION AND GITHUB ACTIONS INTEGRATION
# Detects stale locks and prepares approval request data
# ==============================================================================

set -e

TABLE_NAME="text2agent-terraform-state-lock"
REGION="eu-west-2"

echo "🔍 Checking for stale Terraform state locks..."
echo "=============================================="

# Check if any locks exist
LOCKS=$(aws dynamodb scan \
    --table-name "$TABLE_NAME" \
    --region "$REGION" \
    --filter-expression "attribute_exists(#info)" \
    --expression-attribute-names '{"#info": "Info"}' \
    --query 'Items[].Info.S' \
    --output text 2>/dev/null || echo "")

if [ -z "$LOCKS" ]; then
    echo "✅ No active locks found - all clear!"
    echo "STALE_LOCKS_FOUND=false" >> $GITHUB_ENV
    exit 0
fi

echo "🚨 Found active locks!"
echo "STALE_LOCKS_FOUND=true" >> $GITHUB_ENV

# Process lock information
LOCK_DETAILS=""
LOCK_IDS=""
LOCK_COUNT=0

echo "$LOCKS" | while IFS= read -r lock_json; do
    if [ -n "$lock_json" ]; then
        LOCK_COUNT=$((LOCK_COUNT + 1))
        
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
        
        # Build details for GitHub summary
        LOCK_DETAILS="${LOCK_DETAILS}
**Lock ${LOCK_COUNT}:**
- **ID:** \`${LOCK_ID}\`
- **Operation:** ${OPERATION}
- **Created:** ${CREATED}
- **Who:** ${WHO}
"
        
        # Collect lock IDs
        if [ -n "$LOCK_IDS" ]; then
            LOCK_IDS="${LOCK_IDS},${LOCK_ID}"
        else
            LOCK_IDS="$LOCK_ID"
        fi
    fi
done

# Export to GitHub environment
{
    echo "LOCK_DETAILS<<EOF"
    echo "$LOCK_DETAILS"
    echo "EOF"
} >> $GITHUB_ENV

echo "LOCK_IDS=$LOCK_IDS" >> $GITHUB_ENV
echo "LOCK_COUNT=$LOCK_COUNT" >> $GITHUB_ENV

# Display summary
echo ""
echo "📋 Lock Summary:"
echo "   Count: $LOCK_COUNT"
echo "   IDs: $LOCK_IDS"
echo ""
echo "🔄 Workflow will now pause for manual approval..."
echo "   You'll see an approval request in GitHub Actions"
echo "   Review the lock details and approve to unlock automatically" 