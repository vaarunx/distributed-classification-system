#!/bin/bash
# destroy.sh - Destroy infrastructure using Terraform

set -e

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${RED}=== Terraform Destroy Script ===${NC}"
echo ""

# Navigate to terraform directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TERRAFORM_DIR="$SCRIPT_DIR/../terraform"

if [ ! -d "$TERRAFORM_DIR" ]; then
    echo -e "${RED}Error: Terraform directory not found at $TERRAFORM_DIR${NC}"
    exit 1
fi

cd "$TERRAFORM_DIR"

# Check if terraform is initialized
if [ ! -d ".terraform" ]; then
    echo -e "${YELLOW}Terraform not initialized. Initializing...${NC}"
    terraform init
    echo ""
fi

# Show what will be destroyed
echo -e "${YELLOW}Running Terraform plan to show what will be destroyed...${NC}"
terraform plan -destroy
echo ""

# Ask for confirmation
echo -e "${RED}WARNING: This will destroy all infrastructure!${NC}"
read -p "Are you sure you want to proceed? Type 'yes' to confirm: " confirm

if [ "$confirm" != "yes" ]; then
    echo -e "${YELLOW}Destroy cancelled${NC}"
    exit 0
fi

# Destroy
echo -e "${YELLOW}Destroying infrastructure...${NC}"
terraform destroy -auto-approve

echo ""
echo -e "${GREEN}✓ Infrastructure destroyed${NC}"

