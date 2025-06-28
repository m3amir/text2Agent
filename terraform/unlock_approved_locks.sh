#!/bin/bash

# ==============================================================================
# AUTOMATIC LOCK UNLOCK AFTER APPROVAL
# Unlocks the stale locks that were approved via GitHub Actions environment
# ==============================================================================

set -e

echo "🔓 Processing approved lock unlock request..."
echo "============================================"

# Check if lock IDs were provided
if [ -z "$LOCK_IDS" ]; then
    echo "❌ No lock IDs provided in environment variable LOCK_IDS"
    exit 1
fi

echo "📋 Approved locks to unlock: $LOCK_IDS"
echo ""

# Split comma-separated lock IDs and unlock each
IFS=',' read -ra LOCK_ARRAY <<< "$LOCK_IDS"
UNLOCK_COUNT=0
FAILED_COUNT=0

for LOCK_ID in "${LOCK_ARRAY[@]}"; do
    LOCK_ID=$(echo "$LOCK_ID" | xargs)  # Trim whitespace
    
    if [ -n "$LOCK_ID" ]; then
        echo "🔓 Unlocking lock: $LOCK_ID"
        
        if terraform force-unlock -force "$LOCK_ID"; then
            echo "✅ Successfully unlocked: $LOCK_ID"
            UNLOCK_COUNT=$((UNLOCK_COUNT + 1))
        else
            echo "❌ Failed to unlock: $LOCK_ID"
            FAILED_COUNT=$((FAILED_COUNT + 1))
        fi
        echo ""
    fi
done

# Summary
echo "📊 Unlock Summary:"
echo "   ✅ Successfully unlocked: $UNLOCK_COUNT"
echo "   ❌ Failed to unlock: $FAILED_COUNT"
echo ""

if [ "$FAILED_COUNT" -gt 0 ]; then
    echo "⚠️ Some locks failed to unlock. Check the output above."
    echo "You may need to manually run: terraform force-unlock [LOCK_ID]"
    exit 1
else
    echo "🎉 All approved locks successfully unlocked!"
    echo "Terraform operations can now proceed normally."
fi 