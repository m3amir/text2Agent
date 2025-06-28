#!/bin/bash

# ==============================================================================
# REAL-TIME TERRAFORM LOCK MONITOR
# Continuously monitors the DynamoDB lock table to see lock activity
# ==============================================================================

TABLE_NAME="text2agent-terraform-state-lock"
REGION="eu-west-2"

echo "🔍 Real-time Terraform Lock Monitor"
echo "==================================="
echo "Table: $TABLE_NAME"
echo "Region: $REGION"
echo "Press Ctrl+C to stop monitoring"
echo ""

# Track previous state to detect changes
PREV_COUNT=0
PREV_LOCKS=""

while true; do
    TIMESTAMP=$(date '+%H:%M:%S')
    
    # Get current lock count
    CURRENT_COUNT=$(aws dynamodb scan \
        --table-name "$TABLE_NAME" \
        --region "$REGION" \
        --query 'Count' \
        --output text 2>/dev/null || echo "0")
    
    # Get current locks with Info attribute
    CURRENT_LOCKS=$(aws dynamodb scan \
        --table-name "$TABLE_NAME" \
        --region "$REGION" \
        --filter-expression "attribute_exists(#info)" \
        --expression-attribute-names '{"#info": "Info"}' \
        --query 'Items[].Info.S' \
        --output text 2>/dev/null || echo "")
    
    INFO_COUNT=$(echo "$CURRENT_LOCKS" | wc -w)
    
    # Detect changes
    if [ "$CURRENT_COUNT" != "$PREV_COUNT" ] || [ "$CURRENT_LOCKS" != "$PREV_LOCKS" ]; then
        echo "[$TIMESTAMP] 🔄 CHANGE DETECTED:"
        echo "  Total items: $PREV_COUNT → $CURRENT_COUNT"
        echo "  Items with Info: $(echo "$PREV_LOCKS" | wc -w) → $INFO_COUNT"
        
        if [ "$CURRENT_COUNT" -gt 0 ]; then
            echo ""
            echo "  📋 Current table contents:"
            aws dynamodb scan \
                --table-name "$TABLE_NAME" \
                --region "$REGION" \
                --output json 2>/dev/null | jq -r '.Items[] | @json' | while read -r item; do
                
                LOCK_ID=$(echo "$item" | jq -r '.LockID.S // "unknown"')
                INFO=$(echo "$item" | jq -r '.Info.S // ""')
                
                echo "    Lock: ${LOCK_ID:0:12}..."
                
                if [ -n "$INFO" ]; then
                    # Parse lock info
                    OPERATION=$(echo "$INFO" | jq -r '.Operation // "unknown"' 2>/dev/null || echo "parse error")
                    WHO=$(echo "$INFO" | jq -r '.Who // "unknown"' 2>/dev/null || echo "parse error")
                    CREATED=$(echo "$INFO" | jq -r '.Created // "unknown"' 2>/dev/null || echo "parse error")
                    
                    echo "      Operation: $OPERATION"
                    echo "      Who: $WHO"
                    echo "      Created: $CREATED"
                else
                    echo "      No Info attribute (this is the problem!)"
                fi
                echo ""
            done
        else
            echo "  ✅ Table is empty"
        fi
        
        echo "----------------------------------------"
        
        # Update previous state
        PREV_COUNT=$CURRENT_COUNT
        PREV_LOCKS=$CURRENT_LOCKS
    else
        # No change, just show a heartbeat
        echo "[$TIMESTAMP] ❤️  Monitoring... (Total: $CURRENT_COUNT, Info: $INFO_COUNT)"
    fi
    
    sleep 5
done 