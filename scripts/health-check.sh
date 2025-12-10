#!/bin/bash
# health-check.sh - Quick health check of deployed services

set -e

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}=== Health Check ===${NC}"
echo ""

# Get ALB endpoint from Terraform
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TERRAFORM_DIR="$SCRIPT_DIR/../terraform"

if [ ! -d "$TERRAFORM_DIR" ]; then
    echo -e "${RED}Error: Terraform directory not found${NC}"
    exit 1
fi

cd "$TERRAFORM_DIR"

echo -e "${YELLOW}Getting ALB endpoint from Terraform...${NC}"
ALB_ENDPOINT=$(terraform output -raw alb_endpoint 2>/dev/null || echo "")

if [ -z "$ALB_ENDPOINT" ]; then
    echo -e "${RED}Error: Could not get ALB endpoint from Terraform${NC}"
    echo "  Make sure infrastructure is deployed: ./scripts/deploy.sh"
    exit 1
fi

echo -e "${GREEN}ALB Endpoint: $ALB_ENDPOINT${NC}"
echo ""

# Check backend health
echo -e "${YELLOW}Checking backend health...${NC}"
HEALTH_RESPONSE=$(curl -s -w "\n%{http_code}" "$ALB_ENDPOINT/health" || echo -e "\n000")
HTTP_CODE=$(echo "$HEALTH_RESPONSE" | tail -n1)
HEALTH_BODY=$(echo "$HEALTH_RESPONSE" | head -n-1)

if [ "$HTTP_CODE" = "200" ]; then
    echo -e "${GREEN}✓ Backend is healthy${NC}"
    echo "  Response: $HEALTH_BODY"
else
    echo -e "${RED}✗ Backend health check failed (HTTP $HTTP_CODE)${NC}"
fi
echo ""

# Check ECS services
echo -e "${YELLOW}Checking ECS services...${NC}"

# Get cluster name from Terraform
CLUSTER_NAME=$(terraform output -json aws_resources 2>/dev/null | grep -o '"cluster_name":"[^"]*' | cut -d'"' -f4 || echo "")

if [ -n "$CLUSTER_NAME" ]; then
    # Check backend service
    BACKEND_SERVICE="${CLUSTER_NAME%-cluster}-backend-service"
    BACKEND_RUNNING=$(aws ecs describe-services \
        --cluster "$CLUSTER_NAME" \
        --services "$BACKEND_SERVICE" \
        --query 'services[0].runningCount' \
        --output text 2>/dev/null || echo "0")
    
    BACKEND_DESIRED=$(aws ecs describe-services \
        --cluster "$CLUSTER_NAME" \
        --services "$BACKEND_SERVICE" \
        --query 'services[0].desiredCount' \
        --output text 2>/dev/null || echo "0")
    
    if [ "$BACKEND_RUNNING" = "$BACKEND_DESIRED" ] && [ "$BACKEND_RUNNING" != "0" ]; then
        echo -e "${GREEN}✓ Backend service: $BACKEND_RUNNING/$BACKEND_DESIRED running${NC}"
    else
        echo -e "${YELLOW}⚠ Backend service: $BACKEND_RUNNING/$BACKEND_DESIRED running${NC}"
    fi
    
    # Check ML service
    ML_SERVICE="${CLUSTER_NAME%-cluster}-ml-service"
    ML_RUNNING=$(aws ecs describe-services \
        --cluster "$CLUSTER_NAME" \
        --services "$ML_SERVICE" \
        --query 'services[0].runningCount' \
        --output text 2>/dev/null || echo "0")
    
    ML_DESIRED=$(aws ecs describe-services \
        --cluster "$CLUSTER_NAME" \
        --services "$ML_SERVICE" \
        --query 'services[0].desiredCount' \
        --output text 2>/dev/null || echo "0")
    
    if [ "$ML_RUNNING" = "$ML_DESIRED" ] && [ "$ML_RUNNING" != "0" ]; then
        echo -e "${GREEN}✓ ML service: $ML_RUNNING/$ML_DESIRED running${NC}"
    else
        echo -e "${YELLOW}⚠ ML service: $ML_RUNNING/$ML_DESIRED running${NC}"
    fi
else
    echo -e "${YELLOW}⚠ Could not get cluster name from Terraform${NC}"
    echo "  ECS service status check skipped"
fi

echo ""
echo -e "${BLUE}=== Health Check Complete ===${NC}"

