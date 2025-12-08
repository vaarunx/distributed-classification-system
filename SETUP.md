# Setup Guide - Distributed Image Classification System

This guide will walk you through cloning the repository, deploying the AWS infrastructure, and running the Streamlit dashboard.

## Table of Contents

1. [Prerequisites Installation](#1-prerequisites-installation)
2. [AWS Account Setup](#2-aws-account-setup)
3. [Repository Setup](#3-repository-setup)
4. [Project File Structure & Purpose](#4-project-file-structure--purpose)
5. [Infrastructure Deployment](#5-infrastructure-deployment)
6. [Running the Dashboard](#6-running-the-dashboard)
7. [Running Tests](#7-running-tests)
8. [Verification & Testing](#8-verification--testing)
9. [Troubleshooting](#9-troubleshooting)

---

## 1. Prerequisites Installation

Before you begin, you need to install and configure the following tools:

### 1.1 AWS CLI

**Installation:**

- **Windows:** Download the MSI installer from [AWS CLI Downloads](https://aws.amazon.com/cli/)
- **macOS:** `brew install awscli`
- **Linux:** `sudo apt-get install awscli` or `sudo yum install awscli`

**Verify installation:**
```bash
aws --version
# Should output: aws-cli/2.x.x
```

### 1.2 Terraform

**Installation:**

- **Windows:** Download from [Terraform Downloads](https://www.terraform.io/downloads) or use `choco install terraform`
- **macOS:** `brew install terraform`
- **Linux:** Download from [Terraform Downloads](https://www.terraform.io/downloads)

**Verify installation:**
```bash
terraform version
# Should output: Terraform v1.0.0 or higher
```

### 1.3 Docker

**Installation:**

- **Windows/macOS:** Download [Docker Desktop](https://www.docker.com/products/docker-desktop)
- **Linux:** Follow [Docker Engine installation guide](https://docs.docker.com/engine/install/)

**Verify installation:**
```bash
docker --version
docker ps
# Docker daemon should be running
```

### 1.4 Python 3.x

**Installation:**

- **Windows:** Download from [Python Downloads](https://www.python.org/downloads/)
- **macOS:** `brew install python3`
- **Linux:** `sudo apt-get install python3 python3-pip`

**Verify installation:**
```bash
python3 --version
pip3 --version
```

---

## 2. AWS Account Setup

### 2.1 AWS Account Requirements

- An active AWS account
- Appropriate IAM permissions to create:
  - ECS clusters and services
  - ECR repositories
  - S3 buckets
  - SQS queues
  - DynamoDB tables
  - VPC, subnets, security groups
  - Application Load Balancer
  - IAM roles and policies
  - CloudWatch logs

### 2.2 Configure AWS CLI Credentials

Run the following command and follow the prompts:

```bash
aws configure
```

You'll be asked for:
- **AWS Access Key ID:** Your AWS access key
- **AWS Secret Access Key:** Your AWS secret key
- **Default region name:** `us-east-1` (or your preferred region)
- **Default output format:** `json`

**Verify configuration:**
```bash
aws sts get-caller-identity
# Should output your AWS account ID and user ARN
```

### 2.3 IAM Role (Optional)

If you're using a lab environment with a pre-configured IAM role (e.g., `LabRole`), ensure it has the necessary permissions. The Terraform configuration will use this role if available.

---

## 3. Repository Setup

### 3.1 Clone the Repository

```bash
git clone <repository-url>
cd distributed-classification-system/distributed-classification-system
```

Replace `<repository-url>` with the actual Git repository URL.

### 3.2 Verify Repository Structure

You should see the following main directories:

```
distributed-classification-system/
├── backend-service/      # Go backend API service
├── ml-service/           # Python ML classification service
├── streamlit-app/         # Streamlit web dashboard
├── terraform/             # Infrastructure as Code
├── scripts/               # Utility scripts
├── load-tests/            # Load testing infrastructure
├── docker-compose.yml     # Local development setup
└── README.md              # Project overview
```

---

## 4. Project File Structure & Purpose

Understanding the project structure will help you navigate and work with the codebase.

### 4.1 Core Service Directories

#### `backend-service/`
**Purpose:** Go-based REST API that handles job submission, status tracking, and image management.

**Key Files:**
- `main.go` - Entry point, sets up HTTP server and routes
- `handlers/handlers.go` - HTTP request handlers (submit, status, result, etc.)
- `services/` - AWS service integrations (S3, SQS, DynamoDB)
- `config/config.go` - Configuration loading from environment variables
- `Dockerfile` - Container image definition for backend service

#### `ml-service/`
**Purpose:** Python FastAPI service that processes classification jobs from SQS queue.

**Key Files:**
- `main.py` - FastAPI application entry point
- `sqs_worker.py` - SQS queue worker that processes jobs
- `controllers/classification_controller.py` - ML model controllers (MobileNet, CLIP)
- `models/` - ML model implementations
- `requirements.txt` - Python dependencies
- `Dockerfile` - Container image definition for ML service

#### `streamlit-app/`
**Purpose:** Web-based dashboard for uploading images, submitting jobs, and viewing results.

**Key Files:**
- `app.py` - Main Streamlit application
- `utils/api_client.py` - Backend API client wrapper
- `utils/s3_client.py` - S3 upload utilities
- `requirements.txt` - Python dependencies (Streamlit, requests, boto3, etc.)
- `Dockerfile` - Container image definition for Streamlit app

### 4.2 Infrastructure Directory

#### `terraform/`
**Purpose:** Infrastructure as Code - defines all AWS resources.

**Key Files:**
- `main.tf` - Root Terraform configuration, module declarations
- `variables.tf` - Input variables (project name, region, resource sizes)
- `outputs.tf` - Output values (ALB endpoint, cluster names, etc.)
- `modules/` - Reusable Terraform modules:
  - `container-registry/` - ECR repositories and Docker image builds
  - `networking/` - VPC, subnets, security groups
  - `storage/` - S3 buckets and DynamoDB tables
  - `queues/` - SQS queues
  - `load-balancer/` - Application Load Balancer
  - `ecs-cluster/` - ECS cluster and services

### 4.3 Scripts Directory

#### `scripts/`
**Purpose:** Utility scripts for deployment, testing, and management.

**Deployment Scripts:**
- `deploy.sh` - Main deployment script (runs terraform init, plan, apply)
- `destroy.sh` - Teardown script (runs terraform destroy)

**Service Management:**
- `scale-backend-service.sh <count>` - Scale backend ECS service to target count
- `scale-ml-service.sh <count>` - Scale ML ECS service to target count
- `manage-autoscaling.sh <status>` - Suspend/resume autoscaling (status: suspend/resume)

**Testing Scripts:**
- `test-api.sh [endpoint]` - Basic API endpoint tests
- `test-deployment.sh` - End-to-end deployment verification
- `health-check.sh` - Quick health check of deployed services
- `run-all-tests.sh` - Run all load tests sequentially
- `run-load-test.sh <test_name>` - Run a specific load test scenario

**Dashboard:**
- `run-streamlit.sh` - Launch Streamlit dashboard locally

**Utilities:**
- `pre-upload-images.sh` / `pre-upload-images.py` - Upload test images to S3
- `collect-metrics.py` - Collect CloudWatch metrics during tests
- `generate-report.sh` - Generate test reports and graphs
- `wait-for-queue-empty.sh` - Wait for SQS queue to clear
- `wait-for-autoscaling-ready.sh` - Wait for autoscaling to stabilize

### 4.4 Configuration Files

#### `docker-compose.yml`
**Purpose:** Local development setup using LocalStack (AWS service emulator).

**Usage:** Run services locally without AWS:
```bash
docker-compose up
```

#### `s3_keys.json`
**Purpose:** Mapping file of uploaded test images (generated by pre-upload scripts).

#### `terraform/terraform.tfvars` (optional)
**Purpose:** Custom Terraform variable values. If not present, defaults from `variables.tf` are used.

**Example:**
```hcl
project_name = "my-classifier"
environment  = "dev"
backend_cpu  = 512
backend_memory = 1024
ml_cpu = 2048
ml_memory = 8192
```

### 4.5 Load Testing Directory

#### `load-tests/`
**Purpose:** Locust-based load testing infrastructure.

**Key Files:**
- `locustfile.py` - Locust test scenarios
- `test_scenarios/` - Individual test scenario definitions:
  - `autoscaling_response.py` - Test autoscaling response time
  - `queue_explosion.py` - Test queue depth handling
  - `sustained_load.py` - Test sustained load stability
  - `throughput_scaling.py` - Test throughput scaling curve
- `analysis/` - Test result analysis and graph generation
- `config.py` - Load test configuration
- `requirements.txt` - Python dependencies for load tests

---

## 5. Infrastructure Deployment

### 5.1 Quick Deployment (Recommended)

Use the provided deployment script:

```bash
./scripts/deploy.sh
```

This script will:
1. Check prerequisites (Terraform, AWS CLI, Docker)
2. Verify AWS credentials
3. Initialize Terraform
4. Run `terraform plan`
5. Ask for confirmation
6. Run `terraform apply`
7. Wait for services to be healthy
8. Display deployment outputs

### 5.2 Manual Deployment

If you prefer to deploy manually:

```bash
cd terraform

# Initialize Terraform
terraform init

# Review the deployment plan
terraform plan

# Apply the configuration (creates all AWS resources)
terraform apply
```

When prompted, type `yes` to confirm.

### 5.3 What Happens During Deployment

Terraform will automatically:

1. **Create ECR Repositories** - Container registries for backend and ML service images
2. **Build Docker Images** - Builds images locally from `backend-service/` and `ml-service/`
3. **Push to ECR** - Uploads images to AWS ECR
4. **Create Networking** - VPC, subnets, security groups
5. **Create Storage** - S3 buckets (input/output) and DynamoDB table
6. **Create Queues** - SQS queues for job requests and status updates
7. **Create Load Balancer** - Application Load Balancer (ALB)
8. **Create ECS Cluster** - Container orchestration cluster
9. **Deploy Services** - Backend and ML services on ECS
10. **Configure IAM** - Roles and policies for services

**Expected Duration:** 10-15 minutes (first deployment may take longer)

### 5.4 Get Deployment Outputs

After deployment completes, get the backend API endpoint:

```bash
cd terraform
terraform output alb_endpoint
```

Example output:
```
"http://distributed-classifier-alb-123456789.us-east-1.elb.amazonaws.com"
```

Save this URL - you'll need it for the dashboard and testing.

### 5.5 Verify Services Are Running

Wait a few minutes for ECS services to start, then check:

```bash
./scripts/health-check.sh
```

Or manually check:
```bash
# Get ALB endpoint
ALB_ENDPOINT=$(terraform -chdir=terraform output -raw alb_endpoint)

# Check health
curl $ALB_ENDPOINT/health
```

Expected response:
```json
{"status":"healthy"}
```

---

## 6. Running the Dashboard

The Streamlit dashboard provides a web interface for:
- Uploading images to S3
- Submitting classification jobs
- Monitoring job status
- Viewing results
- Managing image gallery

### 6.1 Install Streamlit Dependencies

The dashboard script will automatically check and install dependencies, but you can install manually:

```bash
cd streamlit-app
pip3 install -r requirements.txt
```

### 6.2 Run the Dashboard

**Option 1: Using the script (Recommended)**

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

### 6.3 Access the Dashboard

Open your browser and navigate to:

```
http://localhost:8501
```

If port 8501 is in use, the script will try 8502, 8503, etc. Check the terminal output for the actual port.

### 6.4 Configure Backend URL

If the dashboard doesn't connect automatically:

1. Open the sidebar (click the hamburger menu)
2. Find "Backend URL" section
3. Enter your ALB endpoint (from `terraform output alb_endpoint`)
4. Click "Test Connection" to verify

### 6.5 Dashboard Features

- **Upload Images:** Upload multiple images directly to S3
- **Image Gallery:** Browse, search, and delete images
- **Submit Jobs:** Create classification jobs (MobileNet or custom CLIP)
- **Job Status:** Monitor active jobs in real-time
- **Job History:** View all past jobs with filtering
- **Custom Categories:** Save and reuse label sets

---

## 7. Running Tests

The project includes several test scripts to verify functionality and performance.

### 7.1 Basic API Tests

**Purpose:** Test individual API endpoints.

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

### 7.2 End-to-End Deployment Test

**Purpose:** Comprehensive test of the entire deployment workflow.

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

### 7.3 Health Check

**Purpose:** Quick verification that services are running.

```bash
./scripts/health-check.sh
```

**What it checks:**
- Backend API health endpoint
- ECS service running counts
- Service desired vs. running task counts

### 7.4 Load Tests

**Purpose:** Performance and scalability testing under load.

#### Prerequisites for Load Tests

1. **Pre-upload test images:**
```bash
# Upload images to S3 (creates s3_keys.json)
./scripts/pre-upload-images.sh
```

Or with Python:
```bash
python3 scripts/pre-upload-images.py --folder images --count 1000
```

2. **Install load test dependencies:**
```bash
cd load-tests
pip3 install -r requirements.txt
```

#### Available Load Test Scenarios

1. **Autoscaling Response Test**
   - Tests how quickly autoscaling responds to load
   - Requires autoscaling to be **ENABLED**
   ```bash
   ./scripts/run-load-test.sh autoscaling_response
   ```

2. **Queue Explosion Test**
   - Tests system behavior when queue depth increases rapidly
   - Requires autoscaling to be **ENABLED**
   ```bash
   ./scripts/run-load-test.sh queue_explosion
   ```

3. **Sustained Load Test**
   - Tests system stability under sustained load
   - Requires autoscaling to be **ENABLED**
   ```bash
   ./scripts/run-load-test.sh sustained_load
   ```

4. **Throughput Scaling Test**
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

#### Run All Load Tests

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

#### Load Test Results

After tests complete, view results:

```bash
# Generate reports and graphs
./scripts/generate-report.sh
```

Reports are saved in:
- `load-tests/reports/` - Graphs and visualizations
- `load-tests/results/` - Raw data (CSV, JSON)

### 7.5 Managing Autoscaling for Tests

Some tests require specific autoscaling states:

```bash
# Check current autoscaling status
./scripts/manage-autoscaling.sh status

# Suspend autoscaling (for manual scaling tests)
./scripts/manage-autoscaling.sh suspend

# Resume autoscaling (for autoscaling tests)
./scripts/manage-autoscaling.sh resume
```

---

## 8. Verification & Testing

### 8.1 Verify Deployment

1. **Check Terraform outputs:**
```bash
cd terraform
terraform output
```

2. **Check ECS services:**
```bash
# Get cluster name
CLUSTER_NAME=$(terraform output -raw cluster_name)

# List services
aws ecs list-services --cluster $CLUSTER_NAME

# Check service status
aws ecs describe-services --cluster $CLUSTER_NAME --services <service-name>
```

3. **Check S3 buckets:**
```bash
aws s3 ls | grep distributed-classifier
```

4. **Check SQS queues:**
```bash
aws sqs list-queues | grep distributed-classifier
```

### 8.2 Test API Endpoints

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

### 8.3 Verify Dashboard Connectivity

1. Open dashboard at `http://localhost:8501`
2. Check sidebar for "Backend URL"
3. Click "Test Connection"
4. Should see "✓ Backend is healthy"

---

## 9. Troubleshooting

### 9.1 Common Issues

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
# Start Docker Desktop (Windows/macOS)
# Or start Docker service (Linux)
sudo systemctl start docker
```

**Error: "ConcurrentUpdateException" (Autoscaling)**
```bash
# Wait for autoscaling to stabilize
./scripts/wait-for-autoscaling-ready.sh

# Then retry
terraform apply
```

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

### 9.2 Checking Service Logs

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

### 9.3 Verifying AWS Resources

**List all resources:**
```bash
# ECS clusters
aws ecs list-clusters

# ECS services
aws ecs list-services --cluster <cluster-name>

# S3 buckets
aws s3 ls | grep distributed-classifier

# SQS queues
aws sqs list-queues

# DynamoDB tables
aws dynamodb list-tables

# ECR repositories
aws ecr describe-repositories
```

### 9.4 Scaling Services Manually

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
# Get cluster and service names from Terraform
CLUSTER_NAME=$(terraform -chdir=terraform output -raw cluster_name)
BACKEND_SERVICE=$(terraform -chdir=terraform output -raw backend_service_name)

# Check running count
aws ecs describe-services \
  --cluster $CLUSTER_NAME \
  --services $BACKEND_SERVICE \
  --query 'services[0].runningCount' \
  --output text
```

### 9.5 Cleanup and Reset

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

### 9.6 Getting Help

If you encounter issues not covered here:

1. Check CloudWatch logs for error messages
2. Verify all prerequisites are installed and configured
3. Check AWS service quotas/limits
4. Review Terraform state: `terraform show`
5. Check service task definitions in ECS console

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

For more information, see the main [README.md](README.md).

