#!/bin/bash

# ==============================================================================
# DEBUG TERRAFORM LOCK TABLE
# Quick script to inspect the current state of the DynamoDB lock table
# ==============================================================================

TABLE_NAME="text2agent-terraform-state-lock"
REGION="eu-west-2"

echo "🔍 Debugging Terraform Lock Table"
echo "================================="
echo "Table: $TABLE_NAME"
echo "Region: $REGION"
echo ""

# Check AWS identity
echo "🔧 AWS Identity:"
aws sts get-caller-identity || echo "❌ AWS credentials issue"
echo ""

# Check table exists
echo "🔧 Table Status:"
if aws dynamodb describe-table --table-name "$TABLE_NAME" --region "$REGION" >/dev/null 2>&1; then
    echo "✅ Table exists and accessible"
else
    echo "❌ Table not accessible"
    aws dynamodb describe-table --table-name "$TABLE_NAME" --region "$REGION" 2>&1
    exit 1
fi
echo ""

# Get all items in table
echo "🔍 All Items in Lock Table:"
ALL_ITEMS=$(aws dynamodb scan \
    --table-name "$TABLE_NAME" \
    --region "$REGION" \
    --output json 2>/dev/null || echo '{"Items":[],"Count":0}')

ITEM_COUNT=$(echo "$ALL_ITEMS" | jq -r '.Count // 0')
echo "Total items: $ITEM_COUNT"

if [ "$ITEM_COUNT" -gt 0 ]; then
    echo ""
    echo "📋 Raw Table Contents:"
    echo "$ALL_ITEMS" | jq -r '.Items[] | @json' | while read -r item; do
        echo "----------------------------------------"
        echo "$item" | jq '.'
        echo ""
        
        # Extract and display key fields
        echo "Key fields:"
        echo "  LockID: $(echo "$item" | jq -r '.LockID.S // "not found"')"
        echo "  Info: $(echo "$item" | jq -r '.Info.S // "not found"')"
        echo "  Digest: $(echo "$item" | jq -r '.Digest.S // "not found"')"
        echo ""
        
        # If Info exists, parse it
        INFO=$(echo "$item" | jq -r '.Info.S // ""')
        if [ -n "$INFO" ] && [ "$INFO" != "not found" ]; then
            echo "Parsed Info field:"
            echo "$INFO" | jq '.' || echo "  Failed to parse as JSON: $INFO"
        fi
        echo ""
    done
else
    echo "Table is empty - no locks found"
fi

echo ""
echo "🔍 Testing Lock Detection Query:"
echo "This is the exact query used by the lock detection script..."

LOCKS=$(aws dynamodb scan \
    --table-name "$TABLE_NAME" \
    --region "$REGION" \
    --filter-expression "attribute_exists(#info)" \
    --expression-attribute-names '{"#info": "Info"}' \
    --query 'Items[].Info.S' \
    --output text 2>/dev/null || echo "")

if [ -z "$LOCKS" ]; then
    echo "❌ No locks found with Info attribute"
    echo "This explains why lock detection isn't working!"
else
    echo "✅ Found locks with Info attribute:"
    echo "$LOCKS"
fi

echo ""
echo "🎯 Summary:"
echo "- Total items in table: $ITEM_COUNT"
echo "- Items with 'Info' attribute: $(echo "$LOCKS" | wc -w)"

if [ "$ITEM_COUNT" -gt 0 ] && [ -z "$LOCKS" ]; then
    echo ""
    echo "🚨 PROBLEM IDENTIFIED:"
    echo "The table has items but none have the 'Info' attribute that"
    echo "the lock detection script is looking for. This suggests:"
    echo "1. Wrong table schema/structure"
    echo "2. Different Terraform backend configuration"
    echo "3. Manual items in the table with wrong format"
fi 