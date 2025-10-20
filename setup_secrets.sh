#!/bin/bash

echo "Gathering OCI configuration..."

# Get compartment ID (using root/tenancy compartment)
COMPARTMENT_ID=$(oci iam compartment list --query 'data[0]."compartment-id"' --raw-output)
echo "Compartment ID: $COMPARTMENT_ID"

# Get availability domain
AVAILABILITY_DOMAIN=$(oci iam availability-domain list --compartment-id "$COMPARTMENT_ID" --query 'data[0].name' --raw-output)
echo "Availability Domain: $AVAILABILITY_DOMAIN"

# Get subnet ID (you'll need to create a VCN/subnet first if you don't have one)
SUBNET_ID=$(oci network subnet list --compartment-id "$COMPARTMENT_ID" --query 'data[0].id' --raw-output 2>/dev/null || echo "PLEASE_CREATE_VCN_AND_SUBNET")
echo "Subnet ID: $SUBNET_ID"

# Generate SSH key if doesn't exist
if [ ! -f ~/.ssh/oci_instance_key ]; then
    ssh-keygen -t rsa -b 4096 -f ~/.ssh/oci_instance_key -N ""
fi
SSH_PUBLIC_KEY=$(cat ~/.ssh/oci_instance_key.pub)

# Base64 encode config and key
OCI_CONFIG_B64=$(cat ~/.oci/config | base64 | tr -d '\n')
OCI_PRIVATE_KEY_B64=$(cat ~/.oci/oci_api_key.pem | base64 | tr -d '\n')

# Create .secrets file
cat > .secrets << EOF
OCI_COMPARTMENT_ID=$COMPARTMENT_ID
OCI_AVAILABILITY_DOMAIN=$AVAILABILITY_DOMAIN
OCI_SUBNET_ID=$SUBNET_ID
OCI_SSH_PUBLIC_KEY=$SSH_PUBLIC_KEY
OCI_CONFIG=$OCI_CONFIG_B64
OCI_PRIVATE_KEY=$OCI_PRIVATE_KEY_B64
EOF

echo ".secrets file created successfully!"
