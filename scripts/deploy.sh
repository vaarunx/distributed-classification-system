#!/bin/bash
# deploy.sh - Deploy infrastructure using Terraform

set -e

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}=== Terraform Deployment Script ===${NC}"
echo ""

# Check prerequisites
echo -e "${YELLOW}Checking prerequisites...${NC}"

check_command() {
    if ! command -v $1 &> /dev/null; then
        echo -e "${RED}Error: $1 is not installed${NC}"
        exit 1
    fi
}

check_command terraform
check_command aws
check_command docker

echo -e "${GREEN}✓ All prerequisites met${NC}"
echo ""

# Navigate to terraform directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TERRAFORM_DIR="$SCRIPT_DIR/../terraform"

if [ ! -d "$TERRAFORM_DIR" ]; then
    echo -e "${RED}Error: Terraform directory not found at $TERRAFORM_DIR${NC}"
    exit 1
fi

cd "$TERRAFORM_DIR"

# Check AWS credentials
echo -e "${YELLOW}Checking AWS credentials...${NC}"
if ! aws sts get-caller-identity &> /dev/null; then
    echo -e "${RED}Error: AWS credentials not configured${NC}"
    exit 1
fi
echo -e "${GREEN}✓ AWS credentials configured${NC}"
echo ""

# Initialize Terraform
echo -e "${YELLOW}Initializing Terraform...${NC}"
terraform init
echo ""

# Plan
echo -e "${YELLOW}Running Terraform plan...${NC}"
terraform plan
echo ""

# Ask for confirmation
read -p "Do you want to apply these changes? (yes/no): " confirm
if [ "$confirm" != "yes" ]; then
    echo -e "${YELLOW}Deployment cancelled${NC}"
    exit 0
fi

# Apply
echo -e "${YELLOW}Applying Terraform configuration...${NC}"
terraform apply -auto-approve
echo ""

# Get outputs
echo -e "${GREEN}=== Deployment Complete ===${NC}"
echo ""
echo -e "${YELLOW}Getting deployment outputs...${NC}"

ALB_ENDPOINT=$(terraform output -raw alb_endpoint 2>/dev/null || echo "")
BACKEND_API_URL=$(terraform output -raw backend_api_url 2>/dev/null || echo "$ALB_ENDPOINT")

echo ""
echo -e "${GREEN}Deployment Information:${NC}"
echo "  ALB Endpoint: $ALB_ENDPOINT"
echo "  Backend API URL: $BACKEND_API_URL"
echo ""

# Wait for services to be healthy
echo -e "${YELLOW}Waiting for services to be healthy...${NC}"
MAX_WAIT=300  # 5 minutes
WAIT_INTERVAL=10
ELAPSED=0

while [ $ELAPSED -lt $MAX_WAIT ]; do
    if curl -s -f "$ALB_ENDPOINT/health" > /dev/null 2>&1; then
        echo -e "${GREEN}✓ Backend service is healthy${NC}"
        break
    fi
    
    echo "  Waiting for services... (${ELAPSED}s/${MAX_WAIT}s)"
    sleep $WAIT_INTERVAL
    ELAPSED=$((ELAPSED + WAIT_INTERVAL))
done

if [ $ELAPSED -ge $MAX_WAIT ]; then
    echo -e "${YELLOW}⚠ Warning: Services may not be fully healthy yet${NC}"
    echo "  You can check status with: ./scripts/health-check.sh"
else
    echo -e "${GREEN}✓ All services are healthy${NC}"
fi

echo ""
echo -e "${GREEN}=== Next Steps ===${NC}"
echo ""
echo "1. Run Streamlit locally:"
echo "   ./scripts/run-streamlit.sh"
echo ""
echo "2. Test the deployment:"
echo "   ./scripts/test-deployment.sh"
echo ""
echo "3. Check service health:"
echo "   ./scripts/health-check.sh"
echo ""
echo -e "${GREEN}Deployment complete!${NC}"

