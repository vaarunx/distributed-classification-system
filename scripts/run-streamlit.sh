#!/bin/bash
# run-streamlit.sh - Run Streamlit app locally with backend URL from Terraform

set -e

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}=== Streamlit Local Run Script ===${NC}"
echo ""

# Get backend API URL - use localhost by default, or from Terraform if BACKEND_API_URL env var is not set
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TERRAFORM_DIR="$SCRIPT_DIR/../terraform"
STREAMLIT_DIR="$SCRIPT_DIR/../streamlit-app"

if [ ! -d "$STREAMLIT_DIR" ]; then
    echo -e "${RED}Error: Streamlit app directory not found${NC}"
    exit 1
fi

# Check if BACKEND_API_URL is set as environment variable
if [ -n "$BACKEND_API_URL" ]; then
    echo -e "${GREEN}Using BACKEND_API_URL from environment: $BACKEND_API_URL${NC}"
else
    # Default to localhost for local development
    BACKEND_API_URL="http://localhost:8080"
    echo -e "${YELLOW}Using localhost backend (default)${NC}"
    echo -e "${BLUE}To use deployed backend, set BACKEND_API_URL environment variable${NC}"
    if [ -d "$TERRAFORM_DIR" ]; then
        echo -e "${BLUE}Or run: export BACKEND_API_URL=\$(terraform -chdir=$TERRAFORM_DIR output -raw backend_api_url)${NC}"
    fi
fi

echo ""

# Check if Streamlit is installed
echo -e "${YELLOW}Checking Streamlit installation...${NC}"
if ! command -v streamlit &> /dev/null; then
    echo -e "${YELLOW}Streamlit not found in PATH. Checking if dependencies are installed...${NC}"
    
    cd "$STREAMLIT_DIR"
    
    if [ ! -f "requirements.txt" ]; then
        echo -e "${RED}Error: requirements.txt not found${NC}"
        exit 1
    fi
    
    # Check if we're in a virtual environment or if packages are installed
    if ! python3 -c "import streamlit" 2>/dev/null; then
        echo -e "${YELLOW}Streamlit not installed. Installing dependencies...${NC}"
        echo "  This may take a few minutes..."
        pip3 install -r requirements.txt
    else
        echo -e "${GREEN}✓ Streamlit dependencies are installed${NC}"
    fi
else
    echo -e "${GREEN}✓ Streamlit is installed${NC}"
fi

# Navigate to Streamlit app directory
cd "$STREAMLIT_DIR"

# Check if port 8501 is available, if not try 8502, 8503
STREAMLIT_PORT=8501
if command -v netstat &> /dev/null; then
    if netstat -ano 2>/dev/null | grep -q ":8501.*LISTENING" || netstat -ano 2>/dev/null | grep -q "8501.*LISTEN"; then
        echo -e "${YELLOW}Port 8501 is in use, trying 8502...${NC}"
        STREAMLIT_PORT=8502
        if netstat -ano 2>/dev/null | grep -q ":8502.*LISTENING" || netstat -ano 2>/dev/null | grep -q "8502.*LISTEN"; then
            echo -e "${YELLOW}Port 8502 is also in use, trying 8503...${NC}"
            STREAMLIT_PORT=8503
        fi
    fi
fi

# Set environment variable and run Streamlit
echo ""
echo -e "${GREEN}Starting Streamlit app...${NC}"
echo -e "${BLUE}Backend API URL: $BACKEND_API_URL${NC}"
echo -e "${BLUE}Local Streamlit URL: http://localhost:$STREAMLIT_PORT${NC}"
echo ""
echo -e "${YELLOW}Press Ctrl+C to stop${NC}"
echo ""

export BACKEND_API_URL="$BACKEND_API_URL"
# Use 127.0.0.1 (localhost only) for local development - safer than 0.0.0.0
streamlit run app.py --server.port=$STREAMLIT_PORT --server.address=127.0.0.1

