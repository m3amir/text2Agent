#!/bin/bash

# ==============================================================================
# STALE LOCK CLEANUP SCRIPT
# Detects and optionally removes stale Terraform state locks
# Run this if you encounter lock acquisition errors
# ==============================================================================

set -e

TABLE_NAME="text2agent-terraform-state-lock"
REGION="eu-west-2"
STATE_PATH="text2agent-terraform-state-eu-west-2/text2agent/production/terraform.tfstate"

echo "🔍 Checking for stale Terraform state locks..."
echo "=============================================="
echo "DynamoDB Table: $TABLE_NAME"
echo "Region: $REGION"
echo ""

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
    exit 0
fi

echo "🚨 Found active locks:"
echo "====================="

# Parse lock information
echo "$LOCKS" | while IFS= read -r lock_json; do
    if [ -n "$lock_json" ]; then
        echo ""
        echo "Lock Details:"
        echo "$lock_json" | python3 -m json.tool 2>/dev/null || echo "$lock_json"
        echo ""
        
        # Extract lock ID for potential cleanup
        LOCK_ID=$(echo "$lock_json" | python3 -c "
import json, sys
try:
    data = json.load(sys.stdin)
    print(data.get('ID', 'unknown'))
except:
    print('unknown')
" 2>/dev/null)
        
        if [ "$LOCK_ID" != "unknown" ]; then
            CREATED=$(echo "$lock_json" | python3 -c "
import json, sys
from datetime import datetime
try:
    data = json.load(sys.stdin)
    created = data.get('Created', '')
    if created:
        dt = datetime.fromisoformat(created.replace('Z', '+00:00'))
        print(f'Created: {dt.strftime(\"%Y-%m-%d %H:%M:%S UTC\")}')
    else:
        print('Created: Unknown')
except:
    print('Created: Parse error')
" 2>/dev/null)
            
            echo "Lock ID: $LOCK_ID"
            echo "$CREATED"
            echo ""
            echo "To remove this stale lock, run:"
            echo "  terraform force-unlock $LOCK_ID"
            echo ""
        fi
    fi
done

echo "⚠️  IMPORTANT:"
echo "   - Only force-unlock if you're sure no other Terraform operations are running"
echo "   - Check GitHub Actions workflows before unlocking"
echo "   - Stale locks are usually from cancelled/failed workflows" 