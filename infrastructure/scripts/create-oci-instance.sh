#!/bin/bash
set -e

INSTANCE_NAME="${INSTANCE_NAME:-better-bundle-ampere-$(date +%Y%m%d-%H%M%S)}"
SHAPE="VM.Standard.A1.Flex"
OCPU_COUNT=4
MEMORY_GB=24
COMPARTMENT_ID="${OCI_COMPARTMENT_ID}"
AVAILABILITY_DOMAIN="${OCI_AVAILABILITY_DOMAIN}"
SUBNET_ID="${OCI_SUBNET_ID}"
IMAGE_ID="${OCI_IMAGE_ID}"
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

check_oci_cli() {
    if ! command -v oci &> /dev/null; then
        print_error "OCI CLI is not installed"
        exit 1
    fi
    print_status "OCI CLI is installed"
}

check_oci_config() {
    if [[ ! -f ~/.oci/config ]] || [[ ! -f ~/.oci/oci_api_key.pem ]]; then
        print_error "OCI CLI is not configured"
        exit 1
    fi
    print_status "OCI CLI is configured"
}

validate_environment() {
    local missing_vars=()
    [[ -z "$COMPARTMENT_ID" ]] && missing_vars+=("OCI_COMPARTMENT_ID")
    [[ -z "$AVAILABILITY_DOMAIN" ]] && missing_vars+=("OCI_AVAILABILITY_DOMAIN")
    [[ -z "$SUBNET_ID" ]] && missing_vars+=("OCI_SUBNET_ID")
    [[ -z "$SSH_PUBLIC_KEY" ]] && missing_vars+=("OCI_SSH_PUBLIC_KEY")
    
    if [[ ${#missing_vars[@]} -gt 0 ]]; then
        print_error "Missing required environment variables: ${missing_vars[*]}"
        exit 1
    fi
    print_status "All required environment variables are set"
}

get_latest_image() {
    if [[ -z "$IMAGE_ID" ]]; then
        print_status "Getting latest Ubuntu 22.04 ARM64 image..."
        IMAGE_ID=$(oci compute image list \
            --compartment-id "$COMPARTMENT_ID" \
            --operating-system "Canonical Ubuntu" \
            --operating-system-version "22.04" \
            --sort-by TIMECREATED \
            --sort-order DESC \
            --query 'data[?contains("display-name", `aarch64`)].id | [0]' \
            --raw-output 2>&1)
        
        if [[ "$IMAGE_ID" == "null" || -z "$IMAGE_ID" || "$IMAGE_ID" == *"Error"* ]]; then
            print_warning "Could not find image dynamically. Using latest known Ubuntu 22.04 ARM64 image..."
            # Latest Ubuntu 22.04 aarch64 image for AP-Mumbai as of Oct 2025
            IMAGE_ID="ocid1.image.oc1.ap-mumbai-1.aaaaaaaarwytomrhnmjfemkilercwi4dgazojqzbuq5yjzkjnub6fxiogmzq"
        fi
        print_status "Using image: $IMAGE_ID"
    fi
}

check_existing_instance() {
    print_status "Checking for existing Ampere A1 instances..."
    local instances=$(oci compute instance list \
        --compartment-id "$COMPARTMENT_ID" \
        --lifecycle-state RUNNING \
        --all 2>/dev/null || echo '{"data":[]}')
    
    local instance_id=$(echo "$instances" | grep -o '"id": "[^"]*"' | head -1 | cut -d'"' -f4)
    
    if [[ -n "$instance_id" && "$instance_id" != "null" ]]; then
        print_status "Found existing instance: $instance_id"
        local public_ip=$(oci compute instance list-vnics \
            --instance-id "$instance_id" \
            --query 'data[0]."public-ip"' \
            --raw-output 2>/dev/null)
        
        if [[ -n "$public_ip" && "$public_ip" != "null" ]]; then
            print_status "Public IP: $public_ip"
            print_status "SSH: ssh ubuntu@$public_ip"
        fi
        print_status "✅ Instance already exists! Exiting."
        [[ -n "$GITHUB_OUTPUT" ]] && echo "instance_id=$instance_id" >> "$GITHUB_OUTPUT"
        [[ -n "$GITHUB_OUTPUT" ]] && echo "public_ip=$public_ip" >> "$GITHUB_OUTPUT"
        [[ -n "$GITHUB_OUTPUT" ]] && echo "already_exists=true" >> "$GITHUB_OUTPUT"
        exit 0
    fi
    print_status "No existing instances. Proceeding with creation."
}

create_instance() {
    print_status "Creating Ampere A1 instance: $INSTANCE_NAME"
    print_status "Config: $OCPU_COUNT OCPU, ${MEMORY_GB}GB RAM"
    
    # Create temp file with SSH key
    local ssh_key_file="/tmp/oci_ssh_key_$$.pub"
    echo "$SSH_PUBLIC_KEY" > "$ssh_key_file"
    
    local attempt=0
    while [[ $attempt -lt $MAX_RETRIES ]]; do
        ((attempt++))
        print_status "Attempt $attempt/$MAX_RETRIES..."
        
        local output
        local exit_code
        output=$(oci compute instance launch \
            --compartment-id "$COMPARTMENT_ID" \
            --availability-domain "$AVAILABILITY_DOMAIN" \
            --display-name "$INSTANCE_NAME" \
            --shape "$SHAPE" \
            --shape-config "{\"ocpus\": $OCPU_COUNT, \"memoryInGBs\": $MEMORY_GB}" \
            --image-id "$IMAGE_ID" \
            --subnet-id "$SUBNET_ID" \
            --assign-public-ip true \
            --ssh-authorized-keys-file "$ssh_key_file" 2>&1) && exit_code=0 || exit_code=$?
        
        # Clean up temp file
        rm -f "$ssh_key_file"
        
        if [[ $exit_code -eq 0 ]]; then
            local instance_id=$(echo "$output" | grep -o '"id": "[^"]*"' | head -1 | cut -d'"' -f4)
            if [[ -n "$instance_id" && "$instance_id" != "null" ]]; then
                print_status "✅ Instance created successfully: $instance_id"
                echo "$instance_id"
                return 0
            fi
        fi
        
        if echo "$output" | grep -qi "out of capacity\|out of host capacity"; then
            print_warning "⚠️  Out of capacity error"
            if [[ $attempt -lt $MAX_RETRIES ]]; then
                print_status "Retrying in $RETRY_INTERVAL seconds... ($attempt/$MAX_RETRIES)"
                sleep $RETRY_INTERVAL
            else
                print_error "Out of capacity after $MAX_RETRIES attempts. Exiting - cron will retry in 30 minutes."
                exit 1
            fi
        else
            print_error "Unexpected error occurred:"
            echo "$output"
            exit 1
        fi
    done
    
    print_error "Failed to create instance after $MAX_RETRIES attempts"
    exit 1
}

wait_for_instance() {
    local instance_id="$1"
    print_status "Waiting for instance to be running..."
    
    for i in {1..60}; do
        local state=$(oci compute instance get --instance-id "$instance_id" --query 'data."lifecycle-state"' --raw-output 2>/dev/null)
        
        if [[ "$state" == "RUNNING" ]]; then
            print_status "✅ Instance is running!"
            return 0
        elif [[ "$state" == "TERMINATED" || "$state" == "TERMINATING" ]]; then
            print_error "Instance failed to start"
            exit 1
        fi
        
        print_status "State: $state ($i/60)"
        sleep 10
    done
    
    print_error "Timeout waiting for instance to reach RUNNING state"
    exit 1
}

get_instance_ip() {
    local instance_id="$1"
    print_status "Getting public IP..."
    
    # Wait a bit for VNIC to be attached
    sleep 5
    
    local public_ip=$(oci compute instance list-vnics \
        --instance-id "$instance_id" \
        --query 'data[0]."public-ip"' \
        --raw-output 2>/dev/null)
    
    if [[ -n "$public_ip" && "$public_ip" != "null" ]]; then
        print_status "Public IP: $public_ip"
        echo "$public_ip"
        return 0
    fi
    
    return 1
}

main() {
    print_status "🚀 Starting Oracle Cloud Ampere A1 instance creation..."
    echo ""
    
    check_oci_cli
    check_oci_config
    validate_environment
    get_latest_image
    
    echo ""
    check_existing_instance
    
    echo ""
    local instance_id
    instance_id=$(create_instance)
    
    echo ""
    wait_for_instance "$instance_id"
    
    echo ""
    local public_ip
    if public_ip=$(get_instance_ip "$instance_id"); then
        echo ""
        print_status "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        print_status "🎉 Instance ready!"
        print_status "Instance ID: $instance_id"
        print_status "Public IP: $public_ip"
        print_status "SSH: ssh ubuntu@$public_ip"
        print_status "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        echo ""
        
        [[ -n "$GITHUB_OUTPUT" ]] && echo "instance_id=$instance_id" >> "$GITHUB_OUTPUT"
        [[ -n "$GITHUB_OUTPUT" ]] && echo "public_ip=$public_ip" >> "$GITHUB_OUTPUT"
        [[ -n "$GITHUB_OUTPUT" ]] && echo "already_exists=false" >> "$GITHUB_OUTPUT"
    else
        print_warning "Instance created but could not get public IP"
        print_status "Instance ID: $instance_id"
        [[ -n "$GITHUB_OUTPUT" ]] && echo "instance_id=$instance_id" >> "$GITHUB_OUTPUT"
        [[ -n "$GITHUB_OUTPUT" ]] && echo "already_exists=false" >> "$GITHUB_OUTPUT"
    fi
    
    print_status "✅ Done!"
}

main "$@"
