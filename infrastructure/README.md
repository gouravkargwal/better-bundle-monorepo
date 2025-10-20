# Oracle Cloud Infrastructure (OCI) Automation

This directory contains scripts and workflows for automatically creating Oracle Cloud Ampere A1 instances.

## Prerequisites

### 1. OCI Account Setup

- Oracle Cloud Free Tier account
- OCI CLI installed and configured
- Required OCI resources (compartment, VCN, subnet)

### 2. Required OCI Resources

Before running the scripts, ensure you have:

- **Compartment ID**: Your OCI compartment
- **Availability Domain**: AD where you want to create the instance
- **Subnet ID**: Subnet with internet gateway for public access
- **SSH Public Key**: Your SSH public key for instance access

### 3. GitHub Secrets Setup

For GitHub Actions, add these secrets to your repository:

```
OCI_CONFIG - Base64 encoded OCI config file
OCI_PRIVATE_KEY - Base64 encoded private key file
OCI_COMPARTMENT_ID - Your OCI compartment ID
OCI_AVAILABILITY_DOMAIN - AD name (e.g., "AD-1")
OCI_SUBNET_ID - Subnet OCID
OCI_SSH_PUBLIC_KEY - Your SSH public key
```

## Usage

### Manual Script Execution

1. Set environment variables:

```bash
export OCI_COMPARTMENT_ID="ocid1.compartment.oc1..xxxxx"
export OCI_AVAILABILITY_DOMAIN="AD-1"
export OCI_SUBNET_ID="ocid1.subnet.oc1..xxxxx"
export OCI_SSH_PUBLIC_KEY="ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABgQC..."
```

2. Run the script:

```bash
./infrastructure/scripts/create-oci-instance.sh
```

### GitHub Actions

1. Go to your repository's Actions tab
2. Select "Create OCI Ampere A1 Instance" workflow
3. Click "Run workflow"
4. Optionally customize instance name, OCPU count, and memory
5. Click "Run workflow"

## Instance Configuration

The script creates an Ampere A1 instance with:

- **Shape**: VM.Standard.A1.Flex
- **OCPUs**: 4 (configurable)
- **Memory**: 24GB (configurable)
- **Boot Volume**: 50GB
- **OS**: Latest Oracle Linux 8
- **Network**: Public IP assigned

## Cost Considerations

- Ampere A1 instances are part of Oracle's Always Free tier
- 4 OCPU + 24GB RAM is within the free tier limits
- No additional charges for Always Free eligible resources

## Troubleshooting

### Common Issues

1. **"Out of capacity" error**: Try different availability domains
2. **Authentication errors**: Verify OCI CLI configuration
3. **Network errors**: Ensure subnet has internet gateway
4. **SSH connection issues**: Verify SSH key is correct

### Getting OCI Resource IDs

```bash
# List compartments
oci iam compartment list

# List availability domains
oci iam availability-domain list

# List subnets
oci network subnet list --compartment-id <COMPARTMENT_ID>

# List images
oci compute image list --compartment-id <COMPARTMENT_ID> --operating-system "Oracle Linux"
```

## Security Notes

- SSH keys are stored securely in GitHub secrets
- OCI credentials are base64 encoded for security
- Instances are created with minimal required permissions
- Consider using instance principals for production workloads
