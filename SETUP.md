# Complete Setup Guide - Distributed Image Classification System

This comprehensive guide will walk you through setting up and deploying the entire distributed image classification system from a **completely fresh system** with no prior setup.

## Table of Contents

1. [System Requirements](#1-system-requirements)
2. [Prerequisites Installation](#2-prerequisites-installation)
3. [AWS Account Setup](#3-aws-account-setup)
4. [Repository Setup](#4-repository-setup)
5. [Understanding the Project Structure](#5-understanding-the-project-structure)
6. [Infrastructure Deployment](#6-infrastructure-deployment)
7. [Running the Dashboard](#7-running-the-dashboard)
8. [Testing the System](#8-testing-the-system)
9. [Load Testing](#9-load-testing)
10. [Troubleshooting](#10-troubleshooting)
11. [Cleanup](#11-cleanup)

---

## 1. System Requirements

### Operating System
- **Windows 10/11** (64-bit)
- **macOS** (10.15 or later)
- **Linux** (Ubuntu 20.04+ or similar)

### Hardware Requirements
- **CPU:** 2+ cores recommended
- **RAM:** 8GB minimum, 16GB recommended
- **Storage:** 20GB free space (for Docker images, dependencies, and models)
- **Network:** Stable internet connection for AWS services and model downloads

### Software Requirements
- Git (for cloning repository)
- Terminal/Command Prompt access
- Administrator/root access (for some installations)

---

## 2. Prerequisites Installation

### 2.1 Install Git

**Windows:**
- Download from [Git for Windows](https://git-scm.com/download/win)
- Run installer with default options
- Verify: `git --version`

**macOS:**
```bash
# Using Homebrew
brew install git

# Or download from https://git-scm.com/download/mac
```

**Linux:**
```bash
sudo apt-get update
sudo apt-get install git
```

**Verify installation:**
```bash
git --version
# Should output: git version 2.x.x or higher
```

### 2.2 Install AWS CLI

**Windows:**
1. Download MSI installer from [AWS CLI Downloads](https://aws.amazon.com/cli/)
2. Run the installer
3. Follow installation wizard

**macOS:**
```bash
# Using Homebrew (recommended)
brew install awscli

# Or using pip
pip3 install awscli
```

**Linux:**
```bash
# Using package manager
sudo apt-get update
sudo apt-get install awscli

# Or using pip
pip3 install --user awscli
```

**Verify installation:**
```bash
aws --version
# Should output: aws-cli/2.x.x
```

### 2.3 Install Terraform

**Windows:**
1. Download from [Terraform Downloads](https://www.terraform.io/downloads)
2. Extract ZIP file
3. Add Terraform directory to PATH environment variable
   - Or use Chocolatey: `choco install terraform`

**macOS:**
```bash
# Using Homebrew (recommended)
brew install terraform

# Or download manually from https://www.terraform.io/downloads
```

**Linux:**
```bash
# Download and install
wget https://releases.hashicorp.com/terraform/1.6.0/terraform_1.6.0_linux_amd64.zip
unzip terraform_1.6.0_linux_amd64.zip
sudo mv terraform /usr/local/bin/
rm terraform_1.6.0_linux_amd64.zip
```

**Verify installation:**
```bash
terraform version
# Should output: Terraform v1.0.0 or higher
```

### 2.4 Install Docker

**Windows/macOS:**
1. Download [Docker Desktop](https://www.docker.com/products/docker-desktop)
2. Install and start Docker Desktop
3. Ensure Docker Desktop is running (check system tray/Applications)

**Linux:**
```bash
# Follow official guide: https://docs.docker.com/engine/install/
# For Ubuntu/Debian:
sudo apt-get update
sudo apt-get install docker.io
sudo systemctl start docker
sudo systemctl enable docker

# Add user to docker group (optional, to run without sudo)
sudo usermod -aG docker $USER
# Log out and back in for group change to take effect
```

**Verify installation:**
```bash
docker --version
docker ps
# Docker daemon should be running (no errors)
```

**Important:** Docker must be running before deploying infrastructure, as Terraform will build Docker images locally.

### 2.5 Install Python 3.x

**Windows:**
1. Download from [Python Downloads](https://www.python.org/downloads/)
2. **Important:** Check "Add Python to PATH" during installation
3. Install Python 3.11 or higher

**macOS:**
```bash
# Using Homebrew (recommended)
brew install python3

# Or download from https://www.python.org/downloads/macos/
```

**Linux:**
```bash
sudo apt-get update
sudo apt-get install python3 python3-pip
```

**Verify installation:**
```bash
python3 --version
# Should output: Python 3.11.x or higher
pip3 --version
# Should output: pip 23.x.x or higher
```

### 2.6 Verify All Prerequisites

Run this checklist to verify everything is installed:

```bash
# Check Git
git --version

# Check AWS CLI
aws --version

# Check Terraform
terraform version

# Check Docker
docker --version
docker ps  # Should not error

# Check Python
python3 --version
pip3 --version
```

All commands should execute without errors.

---

## 3. AWS Account Setup

### 3.1 Create AWS Account

If you don't have an AWS account:
1. Go to [AWS Sign Up](https://aws.amazon.com/)
2. Create a new account (requires credit card, but free tier available)
3. Complete account verification

### 3.2 AWS Account Requirements

Your AWS account needs permissions to create:
- **ECS** (Elastic Container Service) - clusters, services, task definitions
- **ECR** (Elastic Container Registry) - repositories for Docker images
- **S3** (Simple Storage Service) - buckets for input/output images
- **SQS** (Simple Queue Service) - queues for job processing
- **DynamoDB** - table for job tracking
- **VPC** (Virtual Private Cloud) - networking (subnets, security groups)
- **Application Load Balancer (ALB)** - load balancing
- **IAM** (Identity and Access Management) - roles and policies
- **CloudWatch** - logging and monitoring
- **Application Auto Scaling** - autoscaling policies

### 3.3 Configure AWS CLI Credentials

**Option 1: Using AWS CLI (Recommended)**

```bash
aws configure
```

You'll be prompted for:
- **AWS Access Key ID:** Your AWS access key
- **AWS Secret Access Key:** Your AWS secret key
- **Default region name:** `us-east-1` (or your preferred region)
- **Default output format:** `json`

**To get AWS credentials:**
1. Log into [AWS Console](https://console.aws.amazon.com/)
2. Go to IAM → Users → Your User → Security Credentials
3. Click "Create Access Key"
4. Choose "Command Line Interface (CLI)"
5. Download or copy the Access Key ID and Secret Access Key

**Option 2: Using Environment Variables**

```bash
# Windows (PowerShell)
$env:AWS_ACCESS_KEY_ID="your-access-key"
$env:AWS_SECRET_ACCESS_KEY="your-secret-key"
$env:AWS_DEFAULT_REGION="us-east-1"

# macOS/Linux
export AWS_ACCESS_KEY_ID="your-access-key"
export AWS_SECRET_ACCESS_KEY="your-secret-key"
export AWS_DEFAULT_REGION="us-east-1"
```

**Verify AWS configuration:**
```bash
aws sts get-caller-identity
# Should output your AWS account ID and user ARN
```

### 3.4 IAM Role Configuration

The Terraform configuration expects an IAM role named `LabRole` (common in AWS lab environments). If you're using a different setup:

1. **If you have a pre-configured IAM role:**
   - The Terraform configuration will automatically use it
   - Ensure it has the necessary permissions listed above

2. **If you need to create IAM permissions:**
   - The role needs permissions for all AWS services listed in section 3.2
   - You can use AWS managed policies or create custom policies
   - Common policies needed:
     - `AmazonECS_FullAccess`
     - `AmazonEC2ContainerRegistryFullAccess`
     - `AmazonS3FullAccess`
     - `AmazonSQSFullAccess`
     - `AmazonDynamoDBFullAccess`
     - `ElasticLoadBalancingFullAccess`
     - `IAMFullAccess` (for creating service roles)

**Note:** For production, use least-privilege IAM policies. The above are for development/testing.

---

## 4. Repository Setup

### 4.1 Clone the Repository

```bash
# Navigate to your desired directory
cd ~/Desktop  # or wherever you want the project

# Clone the repository (replace with actual URL)
git clone <repository-url>
cd distributed-classification-system/distributed-classification-system
```

**If you don't have the repository URL:**
- Contact your project administrator
- Or if this is a local project, navigate to the project directory directly

### 4.2 Verify Repository Structure

After cloning, you should see this structure:

```
distributed-classification-system/
├── backend-service/          # Go backend API service
│   ├── main.go
│   ├── handlers/
│   ├── services/
│   ├── config/
│   ├── models/
│   ├── Dockerfile
│   └── go.mod
├── ml-service/                # Python ML classification service
│   ├── main.py
│   ├── sqs_worker.py
│   ├── controllers/
│   ├── models/
│   ├── schemas/
│   ├── Dockerfile
│   └── requirements.txt
├── streamlit-app/             # Streamlit web dashboard
│   ├── app.py
│   ├── utils/
│   ├── Dockerfile
│   └── requirements.txt
├── terraform/                 # Infrastructure as Code
│   ├── main.tf
│   ├── variables.tf
│   ├── outputs.tf
│   └── modules/
│       ├── container-registry/
│       ├── networking/
│       ├── storage/
│       ├── queues/
│       ├── load-balancer/
│       └── ecs-cluster/
├── scripts/                   # Utility scripts
│   ├── deploy.sh
│   ├── run-streamlit.sh
│   ├── test-api.sh
│   └── ... (other scripts)
├── load-tests/                # Load testing infrastructure
│   ├── locustfile.py
│   ├── test_scenarios/
│   └── requirements.txt
├── docker-compose.yml         # Local development setup
├── README.md                  # Project overview
└── SETUP.md                   # This file
```

If the structure looks different, verify you're in the correct directory.

---

## 5. Understanding the Project Structure

### 5.1 Core Services

#### Backend Service (`backend-service/`)
- **Language:** Go
- **Purpose:** REST API that handles:
  - Job submission and status tracking
  - Image upload management (presigned URLs)
  - Integration with AWS services (S3, SQS, DynamoDB)
- **Key Files:**
  - `main.go` - HTTP server and routing
  - `handlers/handlers.go` - API endpoint handlers
  - `services/` - AWS service clients (S3, SQS, DynamoDB)
  - `config/config.go` - Configuration management

#### ML Service (`ml-service/`)
- **Language:** Python (FastAPI)
- **Purpose:** Processes classification jobs from SQS queue
- **Models Supported:**
  - **MobileNetV2:** ImageNet classification (1000 classes)
  - **CLIP:** Custom label classification
- **Key Files:**
  - `main.py` - FastAPI application
  - `sqs_worker.py` - SQS queue worker
  - `controllers/classification_controller.py` - ML model controllers
  - `models/` - Model implementations (MobileNet, CLIP)

#### Streamlit App (`streamlit-app/`)
- **Language:** Python (Streamlit)
- **Purpose:** Web-based dashboard for:
  - Uploading images to S3
  - Submitting classification jobs
  - Monitoring job status
  - Viewing results
  - Managing image gallery
- **Key Files:**
  - `app.py` - Main Streamlit application
  - `utils/api_client.py` - Backend API client
  - `utils/s3_client.py` - S3 upload utilities

### 5.2 Infrastructure (Terraform)

#### Terraform Modules

**`container-registry/`**
- Creates ECR repositories
- **Automatically builds Docker images** from source code
- Pushes images to ECR
- No manual Docker commands needed!

**`networking/`**
- Creates VPC with public/private subnets
- Security groups for ALB and ECS services
- Internet gateway and NAT gateway

**`storage/`**
- S3 buckets (input and output)
- DynamoDB table for job tracking

**`queues/`**
- SQS queues (request queue and status queue)

**`load-balancer/`**
- Application Load Balancer (ALB)
- Target groups for backend service
- Health checks

**`ecs-cluster/`**
- ECS cluster
- Backend service task definition and service
- ML service task definition and service
- Autoscaling policies
- IAM roles for services

### 5.3 Scripts Directory

**Deployment:**
- `deploy.sh` - Main deployment script (Terraform init, plan, apply)
- `destroy.sh` - Teardown infrastructure

**Service Management:**
- `scale-backend-service.sh <count>` - Scale backend service
- `scale-ml-service.sh <count>` - Scale ML service
- `manage-autoscaling.sh <status>` - Suspend/resume autoscaling

**Testing:**
- `test-api.sh [endpoint]` - Test API endpoints
- `test-deployment.sh` - End-to-end deployment test
- `health-check.sh` - Quick health check

**Dashboard:**
- `run-streamlit.sh` - Launch Streamlit dashboard locally

**Load Testing:**
- `run-load-test.sh <test_name>` - Run specific load test
- `run-all-tests.sh` - Run all load tests sequentially
- `pre-upload-images.sh` - Upload test images to S3
- `generate-report.sh` - Generate test reports

---

## 6. Infrastructure Deployment

### 6.1 Quick Deployment (Recommended)

Use the provided deployment script:

```bash
# From project root
./scripts/deploy.sh
```

**What the script does:**
1. Checks prerequisites (Terraform, AWS CLI, Docker)
2. Verifies AWS credentials
3. Initializes Terraform
4. Runs `terraform plan` (shows what will be created)
5. Asks for confirmation
6. Runs `terraform apply` (creates all resources)
7. Waits for services to be healthy
8. Displays deployment outputs

**Expected Duration:** 10-15 minutes (first deployment)

### 6.2 Manual Deployment

If you prefer manual control:

```bash
cd terraform

# Initialize Terraform (downloads providers)
terraform init

# Review what will be created
terraform plan

# Apply configuration (creates all AWS resources)
terraform apply
```

When prompted, type `yes` to confirm.

### 6.3 What Happens During Deployment

Terraform automatically:

1. **Creates ECR Repositories**
   - `distributed-classifier-backend`
   - `distributed-classifier-ml-service`

2. **Builds Docker Images Locally**
   - Builds backend service image from `backend-service/`
   - Builds ML service image from `ml-service/`
   - Images are built for `linux/amd64` (ECS compatible)

3. **Pushes Images to ECR**
   - Authenticates with ECR
   - Pushes images to AWS

4. **Creates Networking**
   - VPC with public and private subnets
   - Security groups
   - Internet gateway and NAT gateway

5. **Creates Storage**
   - S3 buckets: `distributed-classifier-input-*` and `distributed-classifier-output-*`
   - DynamoDB table: `classification-jobs-*`

6. **Creates Queues**
   - SQS request queue: `classification-requests-*`
   - SQS status queue: `classification-status-*`

7. **Creates Load Balancer**
   - Application Load Balancer (ALB)
   - Target group for backend service
   - Health checks

8. **Creates ECS Cluster**
   - ECS cluster: `distributed-classifier-cluster-*`
   - Backend service (desired count: 1)
   - ML service (desired count: 1)
   - Autoscaling policies

9. **Configures IAM**
   - Task execution roles
   - Task roles with permissions
   - Autoscaling role

### 6.4 Get Deployment Outputs

After deployment completes:

```bash
cd terraform
terraform output
```

**Key outputs:**
- `alb_endpoint` - Backend API URL (e.g., `http://distributed-classifier-alb-123456789.us-east-1.elb.amazonaws.com`)
- `cluster_name` - ECS cluster name
- `backend_service_name` - Backend service name
- `ml_service_name` - ML service name

**Save the ALB endpoint** - you'll need it for the dashboard and testing.

### 6.5 Verify Services Are Running

Wait 2-3 minutes for ECS services to start, then check:

```bash
# From project root
./scripts/health-check.sh
```

Or manually:

```bash
# Get ALB endpoint
ALB_ENDPOINT=$(terraform -chdir=terraform output -raw alb_endpoint)

# Check health
curl $ALB_ENDPOINT/health
```

**Expected response:**
```json
{"status":"healthy","service":"backend-service","time":"2024-01-01T12:00:00Z"}
```

### 6.6 Common Deployment Issues

**Issue: "AWS credentials not configured"**
```bash
# Reconfigure AWS CLI
aws configure

# Or set environment variables
export AWS_ACCESS_KEY_ID="your-key"
export AWS_SECRET_ACCESS_KEY="your-secret"
```

**Issue: "Docker daemon not running"**
- **Windows/macOS:** Start Docker Desktop
- **Linux:** `sudo systemctl start docker`

**Issue: "ConcurrentUpdateException" (Autoscaling)**
```bash
# Wait for autoscaling to stabilize
./scripts/wait-for-autoscaling-ready.sh

# Then retry
cd terraform
terraform apply
```

**Issue: "Insufficient permissions"**
- Check IAM role has required permissions (see section 3.4)
- Verify AWS credentials are correct

---

## 7. Running the Dashboard

The Streamlit dashboard provides a web interface for the entire system.

### 7.1 Install Streamlit Dependencies

The dashboard script will auto-install, but you can install manually:

```bash
cd streamlit-app
pip3 install -r requirements.txt
```

**Dependencies:**
- streamlit
- requests
- boto3
- Pillow
- pandas

### 7.2 Run the Dashboard

**Option 1: Using the Script (Recommended)**

```bash
# From project root
./scripts/run-streamlit.sh
```

The script will:
- Check if Streamlit is installed
- Install dependencies if needed
- Get backend URL from Terraform (or use localhost)
- Start Streamlit on port 8501 (or next available port)

**Option 2: Manual**

```bash
cd streamlit-app

# Set backend URL (get from Terraform)
export BACKEND_API_URL=$(terraform -chdir=../terraform output -raw alb_endpoint)

# Run Streamlit
streamlit run app.py
```

### 7.3 Access the Dashboard

Open your browser and navigate to:

```
http://localhost:8501
```

If port 8501 is in use, the script will try 8502, 8503, etc. Check terminal output for the actual port.

### 7.4 Configure Backend URL

If the dashboard doesn't connect automatically:

1. Open the sidebar (click the hamburger menu ☰)
2. Find "Backend API URL" section
3. Enter your ALB endpoint (from `terraform output alb_endpoint`)
4. Click "🔍 Check Backend Health" to verify

### 7.5 Dashboard Features

#### Upload Images
- Upload multiple images at once
- Direct upload to S3 using presigned URLs
- Progress tracking for batch uploads

#### Image Gallery
- Browse all images in S3
- Search and filter images
- Select multiple images for batch operations
- Delete images individually or in bulk
- Auto-refresh every 30 seconds

#### Submit Classification Jobs
- **Two Job Types:**
  - **Image Classification (MobileNet):** Uses ImageNet labels (1000 classes)
  - **Custom Classification (CLIP):** Use your own custom labels
  
- **Custom Categories:**
  - Save and reuse named label sets (e.g., "Animals", "Vehicles")
  - Manage categories in the sidebar
  - Quick selection when submitting jobs

- **Configuration Options:**
  - Top K predictions (1-10)
  - Confidence threshold (0.0-1.0)
  - Select multiple images per job

#### Job Status & Results
- Monitor active jobs in real-time
- Auto-refresh option (every 5 seconds)
- View detailed results when completed:
  - Summary metrics (total, classified, unknown)
  - Images grouped by label
  - Detailed results table
  - Processing time and model used

#### Job History
- View all submitted jobs with filtering:
  - Filter by status (pending, queued, processing, completed, failed)
  - Filter by job type
- Sortable job list
- Click on any job to view details
- Auto-refresh every 30 seconds

---

## 8. Testing the System

### 8.1 Basic API Tests

Test individual API endpoints:

```bash
./scripts/test-api.sh
```

Or specify an endpoint:

```bash
./scripts/test-api.sh http://your-alb-endpoint.us-east-1.elb.amazonaws.com
```

**What it tests:**
- Health check endpoint
- Presigned URL generation
- Image upload
- Image listing
- Job submission (MobileNet and CLIP)
- Job status polling
- Job results retrieval
- Image deletion

### 8.2 End-to-End Deployment Test

Comprehensive test of the entire workflow:

```bash
./scripts/test-deployment.sh
```

**What it tests:**
- Backend health
- Presigned URL generation
- Image upload to S3
- Image listing
- Job submission
- Job status polling (waits for completion)
- Job results retrieval
- Cleanup (image deletion)

**Expected Duration:** 2-5 minutes (depends on job processing time)

### 8.3 Health Check

Quick verification that services are running:

```bash
./scripts/health-check.sh
```

**What it checks:**
- Backend API health endpoint
- ECS service running counts
- Service desired vs. running task counts

### 8.4 Manual API Testing

**Health Check:**
```bash
ALB_ENDPOINT=$(terraform -chdir=terraform output -raw alb_endpoint)
curl $ALB_ENDPOINT/health
```

**List Images:**
```bash
curl $ALB_ENDPOINT/images
```

**Submit a Test Job:**
```bash
curl -X POST $ALB_ENDPOINT/submit \
  -H "Content-Type: application/json" \
  -d '{
    "job_type": "image_classification",
    "s3_keys": ["test/image.jpg"],
    "top_k": 5,
    "confidence_threshold": 0.5
  }'
```

**Check Job Status:**
```bash
curl $ALB_ENDPOINT/status/{job-id}
```

**Get Job Results:**
```bash
curl $ALB_ENDPOINT/result/{job-id}
```

**List All Jobs:**
```bash
curl "$ALB_ENDPOINT/jobs?limit=100&status=completed"
```

---

## 9. Load Testing

The project includes Locust-based load testing infrastructure.

### 9.1 Prerequisites for Load Tests

**1. Pre-upload test images:**

```bash
# Upload images to S3 (creates s3_keys.json)
./scripts/pre-upload-images.sh
```

Or with Python:

```bash
python3 scripts/pre-upload-images.py --folder images --count 1000
```

**2. Install load test dependencies:**

```bash
cd load-tests
pip3 install -r requirements.txt
```

### 9.2 Available Load Test Scenarios

**1. Autoscaling Response Test**
- Tests how quickly autoscaling responds to load
- Requires autoscaling to be **ENABLED**
```bash
./scripts/run-load-test.sh autoscaling_response
```

**2. Queue Explosion Test**
- Tests system behavior when queue depth increases rapidly
- Requires autoscaling to be **ENABLED**
```bash
./scripts/run-load-test.sh queue_explosion
```

**3. Sustained Load Test**
- Tests system stability under sustained load
- Requires autoscaling to be **ENABLED**
```bash
./scripts/run-load-test.sh sustained_load
```

**4. Throughput Scaling Test**
- Tests throughput scaling curve
- Requires autoscaling to be **DISABLED** (manually scale ML service)
```bash
# First, suspend autoscaling
./scripts/manage-autoscaling.sh suspend

# Scale ML service manually
./scripts/scale-ml-service.sh 50

# Run test
./scripts/run-load-test.sh throughput_scaling

# Scale back down
./scripts/scale-ml-service.sh 1

# Resume autoscaling
./scripts/manage-autoscaling.sh resume
```

### 9.3 Run All Load Tests

Run all load tests sequentially with automatic autoscaling management:

```bash
./scripts/run-all-tests.sh
```

This script will:
- Run tests in the correct order
- Manage autoscaling state automatically
- Wait for queues to empty between tests
- Reset services to baseline between tests
- Generate reports at the end

**Expected Duration:** 30-60 minutes (depends on test configuration)

### 9.4 Managing Autoscaling for Tests

```bash
# Check current autoscaling status
./scripts/manage-autoscaling.sh status

# Suspend autoscaling (for manual scaling tests)
./scripts/manage-autoscaling.sh suspend

# Resume autoscaling (for autoscaling tests)
./scripts/manage-autoscaling.sh resume
```

### 9.5 Generate Reports

After tests complete, generate graphs and analysis:

```bash
./scripts/generate-report.sh
```

Reports are saved in:
- `load-tests/reports/` - Graphs and visualizations (PNG)
- `load-tests/results/` - Raw data (CSV, JSON)

**Graph Types Generated:**
1. Throughput vs Task Count
2. Latency over Time (p50, p95, p99)
3. Autoscaling Response (task count changes)
4. Queue Depth over Time
5. Request Rate over Time
6. Error Rate over Time
7. Resource Utilization (CPU and memory)

---

## 10. Troubleshooting

### 10.1 Common Issues

#### Terraform Apply Fails

**Error: "AWS credentials not configured"**
```bash
# Verify AWS credentials
aws sts get-caller-identity

# Reconfigure if needed
aws configure
```

**Error: "Docker daemon not running"**
```bash
# Windows/macOS: Start Docker Desktop
# Linux:
sudo systemctl start docker
```

**Error: "ConcurrentUpdateException" (Autoscaling)**
```bash
# Wait for autoscaling to stabilize
./scripts/wait-for-autoscaling-ready.sh

# Then retry
cd terraform
terraform apply
```

**Error: "Insufficient permissions"**
- Check IAM role has required permissions
- Verify AWS credentials are correct
- Ensure you're using the correct AWS account

#### Services Won't Start

**Check ECS service logs:**
```bash
# Get log group names
aws logs describe-log-groups | grep distributed-classifier

# View backend logs
aws logs tail /ecs/distributed-classifier/backend --follow

# View ML service logs
aws logs tail /ecs/distributed-classifier/ml-service --follow
```

**Check service status:**
```bash
./scripts/health-check.sh
```

**Common causes:**
- Missing IAM permissions
- Security group rules blocking traffic
- Task definition errors
- Resource limits (CPU/memory)
- Image pull errors (check ECR permissions)

#### Dashboard Won't Connect

**Check backend URL:**
```bash
# Verify ALB endpoint
terraform -chdir=terraform output alb_endpoint

# Test connectivity
curl $(terraform -chdir=terraform output -raw alb_endpoint)/health
```

**Check firewall/network:**
- Ensure port 8501 is not blocked
- Check if backend URL is accessible from your network
- Verify ALB security group allows traffic

#### Load Tests Fail

**Error: "No images in S3"**
```bash
# Pre-upload images
./scripts/pre-upload-images.sh
```

**Error: "Queue not empty"**
```bash
# Wait for queue to clear
./scripts/wait-for-queue-empty.sh
```

**Error: "Autoscaling in wrong state"**
```bash
# Check and fix autoscaling state
./scripts/manage-autoscaling.sh status
./scripts/manage-autoscaling.sh resume  # or suspend
```

### 10.2 Checking Service Logs

**Backend Service:**
```bash
aws logs tail /ecs/distributed-classifier/backend --follow
```

**ML Service:**
```bash
aws logs tail /ecs/distributed-classifier/ml-service --follow
```

**Filter recent errors:**
```bash
aws logs filter-log-events \
  --log-group-name /ecs/distributed-classifier/backend \
  --filter-pattern "ERROR" \
  --start-time $(date -d '1 hour ago' +%s)000
```

### 10.3 Verifying AWS Resources

**List all resources:**
```bash
# ECS clusters
aws ecs list-clusters

# ECS services
CLUSTER_NAME=$(terraform -chdir=terraform output -raw cluster_name)
aws ecs list-services --cluster $CLUSTER_NAME

# S3 buckets
aws s3 ls | grep distributed-classifier

# SQS queues
aws sqs list-queues

# DynamoDB tables
aws dynamodb list-tables

# ECR repositories
aws ecr describe-repositories
```

### 10.4 Scaling Services Manually

**Scale backend service:**
```bash
./scripts/scale-backend-service.sh 2
```

**Scale ML service:**
```bash
./scripts/scale-ml-service.sh 5
```

**Check current counts:**
```bash
CLUSTER_NAME=$(terraform -chdir=terraform output -raw cluster_name)
BACKEND_SERVICE=$(terraform -chdir=terraform output -raw backend_service_name)

aws ecs describe-services \
  --cluster $CLUSTER_NAME \
  --services $BACKEND_SERVICE \
  --query 'services[0].runningCount' \
  --output text
```

### 10.5 Cleanup and Reset

**Empty DynamoDB table:**
```bash
./scripts/clean-dynamodb.sh
# or
python3 scripts/empty-dynamodb.py
```

**Clean load test results:**
```bash
./scripts/clean-load-test-results.sh
```

**Destroy infrastructure:**
```bash
cd terraform
terraform destroy
```

⚠️ **Warning:** This will delete ALL AWS resources. Make sure you want to do this!

---

## 11. Cleanup

### 11.1 Destroy Infrastructure

To completely remove all AWS resources:

```bash
cd terraform
terraform destroy
```

When prompted, type `yes` to confirm.

**What gets destroyed:**
- ECS cluster and services
- ECR repositories (and images)
- S3 buckets (and all objects)
- DynamoDB table (and all data)
- SQS queues
- Load balancer
- VPC and networking
- IAM roles and policies
- CloudWatch log groups

**Note:** Some resources may take a few minutes to fully delete.

### 11.2 Clean Local Files

**Remove Terraform state:**
```bash
cd terraform
rm -rf .terraform terraform.tfstate* .terraform.lock.hcl
```

**Remove Docker images:**
```bash
docker system prune -a
```

**Remove Python cache:**
```bash
find . -type d -name __pycache__ -exec rm -r {} +
find . -type f -name "*.pyc" -delete
```

---

## Quick Reference

### Essential Commands

```bash
# Deploy infrastructure
./scripts/deploy.sh

# Get backend URL
terraform -chdir=terraform output alb_endpoint

# Run dashboard
./scripts/run-streamlit.sh

# Health check
./scripts/health-check.sh

# Run tests
./scripts/test-deployment.sh
./scripts/test-api.sh

# Scale services
./scripts/scale-ml-service.sh 5
./scripts/scale-backend-service.sh 2

# Load tests
./scripts/run-load-test.sh sustained_load
./scripts/run-all-tests.sh
```

### Important URLs

- **Dashboard:** http://localhost:8501
- **Backend API:** `terraform -chdir=terraform output alb_endpoint`
- **AWS Console:** https://console.aws.amazon.com

---

## Next Steps

After setup is complete:

1. ✅ Verify deployment with `./scripts/health-check.sh`
2. ✅ Test API with `./scripts/test-api.sh`
3. ✅ Launch dashboard with `./scripts/run-streamlit.sh`
4. ✅ Upload some test images
5. ✅ Submit a classification job
6. ✅ View results in the dashboard
7. ✅ Explore load testing capabilities

For more information, see the main [README.md](README.md).

---

## Getting Help

If you encounter issues not covered here:

1. Check CloudWatch logs for error messages
2. Verify all prerequisites are installed and configured
3. Check AWS service quotas/limits
4. Review Terraform state: `terraform show`
5. Check service task definitions in ECS console
6. Review the troubleshooting section above

---

**Congratulations!** You've successfully set up the distributed image classification system. 🎉
