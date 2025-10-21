#!/bin/bash

INSTANCE_NAME="${INSTANCE_NAME:-better-bundle-ampere-$(date +%Y%m%d-%H%M%S)}"
SHAPE="VM.Standard.A1.Flex"
OCPU_COUNT=1
MEMORY_GB=6
COMPARTMENT_ID="${OCI_COMPARTMENT_ID}"
AVAILABILITY_DOMAIN="${OCI_AVAILABILITY_DOMAIN}"
SUBNET_ID="${OCI_SUBNET_ID}"
IMAGE_ID="${OCI_IMAGE_ID:-ocid1.image.oc1.ap-mumbai-1.aaaaaaaarwytomrhnmjfemkilercwi4dgazojqzbuq5yjzkjnub6fxiogmzq}"
SSH_PUBLIC_KEY="${OCI_SSH_PUBLIC_KEY}"
MAX_RETRIES="${MAX_RETRIES:-3}"
RETRY_INTERVAL="${RETRY_INTERVAL:-30}"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

print_status() { echo -e "${GREEN}[INFO]${NC} $1"; }
print_warning() { echo -e "${YELLOW}[WARNING]${NC} $1"; }
print_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# Check for existing instances
print_status "🚀 Checking for existing Ampere A1 instances..."
EXISTING_INSTANCES=$(oci compute instance list \
    --compartment-id "$COMPARTMENT_ID" \
    --lifecycle-state RUNNING \
    --all 2>/dev/null)

INSTANCE_ID=$(echo "$EXISTING_INSTANCES" | grep -o '"id": "[^"]*"' | head -1 | cut -d'"' -f4)

if [[ -n "$INSTANCE_ID" && "$INSTANCE_ID" != "null" ]]; then
    print_status "Found existing instance: $INSTANCE_ID"
    PUBLIC_IP=$(oci compute instance list-vnics \
        --instance-id "$INSTANCE_ID" \
        --query 'data[0]."public-ip"' \
        --raw-output 2>/dev/null)
    
    if [[ -n "$PUBLIC_IP" && "$PUBLIC_IP" != "null" ]]; then
        print_status "Public IP: $PUBLIC_IP"
        print_status "SSH: ssh ubuntu@$PUBLIC_IP"
    fi
    
    [[ -n "$GITHUB_OUTPUT" ]] && echo "instance_id=$INSTANCE_ID" >> "$GITHUB_OUTPUT"
    [[ -n "$GITHUB_OUTPUT" ]] && echo "public_ip=$PUBLIC_IP" >> "$GITHUB_OUTPUT"
    [[ -n "$GITHUB_OUTPUT" ]] && echo "already_exists=true" >> "$GITHUB_OUTPUT"
    
    print_status "✅ Instance already exists!"
    exit 0
fi

print_status "No existing instances. Creating new instance..."

# Create temp SSH key file
SSH_KEY_FILE="/tmp/oci_ssh_$$.pub"
echo "$SSH_PUBLIC_KEY" > "$SSH_KEY_FILE"

# Try to create instance
ATTEMPT=0
while [[ $ATTEMPT -lt $MAX_RETRIES ]]; do
    ((ATTEMPT++))
    print_status "Attempt $ATTEMPT/$MAX_RETRIES to create instance: $INSTANCE_NAME"
    
    OUTPUT_FILE="/tmp/oci_output_$$.json"
    
    if oci compute instance launch \
        --compartment-id "$COMPARTMENT_ID" \
        --availability-domain "$AVAILABILITY_DOMAIN" \
        --display-name "$INSTANCE_NAME" \
        --shape "$SHAPE" \
        --shape-config "{\"ocpus\": $OCPU_COUNT, \"memoryInGBs\": $MEMORY_GB}" \
        --image-id "$IMAGE_ID" \
        --subnet-id "$SUBNET_ID" \
        --assign-public-ip true \
        --ssh-authorized-keys-file "$SSH_KEY_FILE" \
        > "$OUTPUT_FILE" 2>&1; then
        
        # Success!
        INSTANCE_ID=$(grep -o '"id": "[^"]*"' "$OUTPUT_FILE" | head -1 | cut -d'"' -f4)
        print_status "✅ Instance created: $INSTANCE_ID"
        
        # Wait for RUNNING state
        print_status "Waiting for instance to be RUNNING..."
        for i in {1..60}; do
            STATE=$(oci compute instance get --instance-id "$INSTANCE_ID" \
                --query 'data."lifecycle-state"' --raw-output 2>/dev/null)
            
            if [[ "$STATE" == "RUNNING" ]]; then
                print_status "✅ Instance is RUNNING!"
                break
            fi
            print_status "State: $STATE ($i/60)"
            sleep 10
        done
        
        # Get public IP
        sleep 5
        PUBLIC_IP=$(oci compute instance list-vnics \
            --instance-id "$INSTANCE_ID" \
            --query 'data[0]."public-ip"' \
            --raw-output 2>/dev/null)
        
        print_status "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        print_status "🎉 Instance ready!"
        print_status "Instance ID: $INSTANCE_ID"
        print_status "Public IP: $PUBLIC_IP"
        print_status "SSH: ssh ubuntu@$PUBLIC_IP"
        print_status "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        
        [[ -n "$GITHUB_OUTPUT" ]] && echo "instance_id=$INSTANCE_ID" >> "$GITHUB_OUTPUT"
        [[ -n "$GITHUB_OUTPUT" ]] && echo "public_ip=$PUBLIC_IP" >> "$GITHUB_OUTPUT"
        [[ -n "$GITHUB_OUTPUT" ]] && echo "already_exists=false" >> "$GITHUB_OUTPUT"
        
        rm -f "$SSH_KEY_FILE" "$OUTPUT_FILE"
        exit 0
    else
        # Failed
        ERROR_MSG=$(cat "$OUTPUT_FILE" 2>/dev/null)
        
        if echo "$ERROR_MSG" | grep -qi "out of capacity\|out of host capacity"; then
            print_warning "⚠️  Out of capacity"
            if [[ $ATTEMPT -lt $MAX_RETRIES ]]; then
                print_status "Retrying in $RETRY_INTERVAL seconds..."
                sleep $RETRY_INTERVAL
            else
                print_error "Out of capacity after $MAX_RETRIES attempts. Cron will retry in 30 min."
                rm -f "$SSH_KEY_FILE" "$OUTPUT_FILE"
                exit 1
            fi
        else
            print_error "Error creating instance:"
            cat "$OUTPUT_FILE"
            rm -f "$SSH_KEY_FILE" "$OUTPUT_FILE"
            exit 1
        fi
    fi
done

rm -f "$SSH_KEY_FILE" "$OUTPUT_FILE"
print_error "Failed after $MAX_RETRIES attempts"
exit 1
