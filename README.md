# Distributed Image Classification System

A scalable, serverless image classification system built on AWS with **automatic Docker builds** handled by Terraform and a **modern Streamlit web interface** for easy interaction. The system supports both MobileNet (ImageNet) and CLIP (custom labels) classification models with automatic scaling capabilities.

## Table of Contents

1. [Overview](#overview)
2. [Key Features](#key-features)
3. [Architecture](#architecture)
4. [Quick Start](#quick-start)
5. [Project Structure](#project-structure)
6. [API Reference](#api-reference)
7. [Streamlit Dashboard](#streamlit-dashboard)
8. [Load Testing](#load-testing)
9. [Configuration](#configuration)
10. [Monitoring & Logging](#monitoring--logging)
11. [Development](#development)

---

## Overview

This distributed image classification system provides:

- **Scalable Infrastructure**: ECS-based services with automatic scaling
- **Multiple ML Models**: MobileNetV2 (ImageNet) and CLIP (custom labels)
- **Queue-Based Processing**: SQS for asynchronous job processing
- **Web Dashboard**: Streamlit interface for easy interaction
- **Infrastructure as Code**: Complete Terraform deployment
- **Automatic Builds**: Docker images built and pushed automatically by Terraform

### Use Cases

- Batch image classification
- Custom label classification
- Image organization and tagging
- ML model performance testing
- Scalability and load testing

---

## Key Features

### Infrastructure

- **No Manual Docker Commands**: Terraform automatically:
  - Builds Docker images from source code
  - Pushes images to ECR
  - Deploys everything in one command
  - Detects code changes and rebuilds only when needed

- **Automatic Scaling**: 
  - ECS service autoscaling based on CPU/memory utilization
  - Queue depth-based scaling for ML service
  - Configurable scaling policies

- **Modular Terraform Design**:
  - Separate modules for networking, storage, queues, load balancing, and ECS
  - Easy to customize and extend
  - Infrastructure as Code best practices

### User Interface

- **Modern Streamlit Web App** with:
  - Image upload and gallery management
  - Custom categories for reusable label sets
  - Job submission and monitoring
  - Complete job history with filtering
  - Real-time status updates
  - Batch operations support

### ML Capabilities

- **MobileNetV2**: ImageNet classification (1000 classes)
- **CLIP**: Custom label classification with zero-shot learning
- **Batch Processing**: Process multiple images per job
- **Confidence Thresholding**: Filter low-confidence predictions
- **Top-K Predictions**: Get top N predictions per image

---

## Architecture

### System Components

```
┌─────────────────┐
│  Streamlit App  │  (Local or Container)
│   (Dashboard)   │
└────────┬────────┘
         │ HTTP
         ▼
┌─────────────────┐
│  Application     │
│  Load Balancer   │
└────────┬────────┘
         │
         ▼
┌─────────────────┐      ┌──────────────┐
│  Backend        │─────▶│  SQS Queue   │
│  Service (ECS)  │      │  (Requests)  │
└────────┬────────┘      └──────┬───────┘
         │                       │
         │                       ▼
         │              ┌─────────────────┐
         │              │  ML Service     │
         │              │  (ECS)          │
         │              └────────┬────────┘
         │                       │
         ▼                       ▼
┌─────────────────┐      ┌─────────────────┐
│  DynamoDB       │      │  S3 Buckets     │
│  (Job Tracking) │      │  (Input/Output) │
└─────────────────┘      └─────────────────┘
```

### AWS Services Used

- **ECS (Elastic Container Service)**: Container orchestration
- **ECR (Elastic Container Registry)**: Docker image storage
- **S3 (Simple Storage Service)**: Image storage (input/output)
- **SQS (Simple Queue Service)**: Job queue and status updates
- **DynamoDB**: Job metadata and results storage
- **Application Load Balancer (ALB)**: Load balancing and routing
- **VPC**: Networking (subnets, security groups)
- **CloudWatch**: Logging and monitoring
- **Application Auto Scaling**: Automatic scaling policies

### Data Flow

1. **Image Upload**: User uploads images via Streamlit → S3 (via presigned URLs)
2. **Job Submission**: User submits classification job → Backend API
3. **Job Queuing**: Backend creates job record in DynamoDB → Sends message to SQS
4. **Job Processing**: ML service polls SQS → Downloads images from S3 → Runs classification
5. **Result Storage**: ML service stores results → Updates DynamoDB → Sends status to SQS
6. **Status Updates**: Backend listens to status queue → Updates job status in DynamoDB
7. **Result Retrieval**: User queries job status/results → Backend returns from DynamoDB

---

## Quick Start

### Prerequisites

- AWS CLI configured with credentials
- Terraform installed (>= 1.0)
- Docker daemon running locally
- Python 3.11+ (for Streamlit dashboard)

**For detailed setup instructions, see [SETUP.md](SETUP.md)**

### Deploy Everything

```bash
# Using the deployment script (recommended)
./scripts/deploy.sh

# Or manually
cd terraform
terraform init
terraform plan
terraform apply
```

**That's it!** Terraform will:
1. Create ECR repositories
2. Build Docker images locally
3. Push images to ECR
4. Deploy all AWS infrastructure
5. Start ECS services

### Get Endpoints

```bash
terraform -chdir=terraform output alb_endpoint
```

### Run Dashboard

```bash
./scripts/run-streamlit.sh
```

Access at `http://localhost:8501`

### Verify Deployment

```bash
./scripts/health-check.sh
```

---

## Project Structure

```
distributed-classification-system/
├── backend-service/          # Go backend API service
│   ├── main.go               # Entry point, HTTP server
│   ├── handlers/             # HTTP request handlers
│   │   └── handlers.go        # Submit, status, result, etc.
│   ├── services/             # AWS service integrations
│   │   ├── s3.go             # S3 operations
│   │   ├── sqs.go            # SQS operations
│   │   └── dynamo.go        # DynamoDB operations
│   ├── config/               # Configuration
│   │   └── config.go        # Environment variable loading
│   ├── models/               # Data models
│   │   └── models.go        # Job, request/response models
│   ├── Dockerfile            # Container image definition
│   └── go.mod                # Go dependencies
│
├── ml-service/               # Python ML classification service
│   ├── main.py               # FastAPI application entry point
│   ├── sqs_worker.py         # SQS queue worker
│   ├── controllers/          # ML model controllers
│   │   └── classification_controller.py
│   ├── models/               # ML model implementations
│   │   ├── mobilenet_model.py
│   │   ├── clip_model.py
│   │   └── base_model.py
│   ├── schemas/              # Pydantic schemas
│   ├── Dockerfile            # Container image definition
│   └── requirements.txt      # Python dependencies
│
├── streamlit-app/            # Streamlit web dashboard
│   ├── app.py                # Main Streamlit application
│   ├── utils/                # Utility modules
│   │   ├── api_client.py    # Backend API client
│   │   └── s3_client.py      # S3 upload utilities
│   ├── Dockerfile            # Container image definition
│   └── requirements.txt      # Python dependencies
│
├── terraform/                # Infrastructure as Code
│   ├── main.tf               # Root configuration
│   ├── variables.tf          # Input variables
│   ├── outputs.tf            # Output values
│   └── modules/              # Reusable Terraform modules
│       ├── container-registry/  # Docker builds & ECR
│       ├── networking/          # VPC, Security Groups
│       ├── storage/             # S3, DynamoDB
│       ├── queues/              # SQS queues
│       ├── load-balancer/       # ALB
│       └── ecs-cluster/         # ECS Services
│
├── scripts/                  # Utility scripts
│   ├── deploy.sh             # Main deployment script
│   ├── destroy.sh            # Teardown script
│   ├── run-streamlit.sh      # Launch dashboard
│   ├── test-api.sh           # API endpoint tests
│   ├── test-deployment.sh    # End-to-end tests
│   ├── health-check.sh       # Health check
│   ├── scale-*.sh            # Service scaling scripts
│   ├── manage-autoscaling.sh # Autoscaling management
│   ├── run-load-test.sh      # Load test runner
│   └── ...                   # Other utility scripts
│
├── load-tests/               # Load testing infrastructure
│   ├── locustfile.py         # Locust test scenarios
│   ├── config.py             # Test configuration
│   ├── test_scenarios/       # Individual test scenarios
│   │   ├── autoscaling_response.py
│   │   ├── queue_explosion.py
│   │   └── sustained_load.py
│   ├── analysis/             # Result analysis
│   │   ├── analyze_results.py
│   │   └── generate_graphs.py
│   ├── reports/              # Generated reports
│   ├── results/              # Test results (CSV, JSON)
│   └── requirements.txt      # Python dependencies
│
├── docker-compose.yml        # Local development setup
├── README.md                 # This file
└── SETUP.md                  # Detailed setup guide
```

---

## API Reference

### Base URL

```
http://<alb-endpoint>
```

Get endpoint: `terraform -chdir=terraform output alb_endpoint`

### Endpoints

#### Health Check

```http
GET /health
```

**Response:**
```json
{
  "status": "healthy",
  "service": "backend-service",
  "time": "2024-01-01T12:00:00Z"
}
```

#### Get Presigned Upload URL

```http
POST /upload-url
Content-Type: application/json

{
  "filename": "image.jpg",
  "content_type": "image/jpeg"
}
```

**Response:**
```json
{
  "upload_url": "https://s3.amazonaws.com/...",
  "s3_key": "uploads/image.jpg"
}
```

#### List Images

```http
GET /images
```

**Response:**
```json
[
  {
    "key": "uploads/image1.jpg",
    "size": 123456,
    "last_modified": "2024-01-01T12:00:00Z"
  }
]
```

#### Delete Image

```http
DELETE /images/{s3_key}
```

#### Submit Classification Job

```http
POST /submit
Content-Type: application/json

{
  "job_type": "image_classification",  // or "custom_classification"
  "s3_keys": ["uploads/image1.jpg", "uploads/image2.jpg"],
  "top_k": 5,
  "confidence_threshold": 0.5,
  "custom_labels": ["cat", "dog", "bird"]  // Required for custom_classification
}
```

**Response:**
```json
{
  "job_id": "uuid-here",
  "status": "queued",
  "message": "Job submitted successfully"
}
```

#### Get Job Status

```http
GET /status/{jobId}
```

**Response:**
```json
{
  "job_id": "uuid-here",
  "status": "processing",  // pending, queued, processing, completed, failed
  "created_at": "2024-01-01T12:00:00Z",
  "updated_at": "2024-01-01T12:05:00Z"
}
```

#### Get Job Result

```http
GET /result/{jobId}
```

**Response:**
```json
{
  "job_id": "uuid-here",
  "status": "completed",
  "result": {
    "total_images": 10,
    "classified": 8,
    "unknown": 2,
    "images": [
      {
        "filename": "image1.jpg",
        "s3_key": "uploads/image1.jpg",
        "top_prediction": "cat",
        "top_confidence": 0.95,
        "all_predictions": [
          {"label": "cat", "score": 0.95},
          {"label": "kitten", "score": 0.03}
        ],
        "processing_time_ms": 150.5
      }
    ]
  }
}
```

#### List All Jobs

```http
GET /jobs?limit=100&status=completed&job_type=image_classification
```

**Query Parameters:**
- `limit` (optional): Maximum number of jobs to return (default: 100)
- `status` (optional): Filter by status (pending, queued, processing, completed, failed)
- `job_type` (optional): Filter by job type (image_classification, custom_classification)

**Response:**
```json
{
  "jobs": [
    {
      "job_id": "uuid-here",
      "status": "completed",
      "job_type": "image_classification",
      "created_at": "2024-01-01T12:00:00Z",
      "completed_at": "2024-01-01T12:05:00Z"
    }
  ],
  "total": 50
}
```

---

## Streamlit Dashboard

### Features

#### 📤 Upload Images
- Upload multiple images at once
- Direct upload to S3 using presigned URLs
- Progress tracking for batch uploads
- View recently uploaded images

#### 🖼️ Image Gallery
- Browse all images in S3
- Search and filter images
- Select multiple images for batch operations
- Delete images individually or in bulk
- Auto-refresh every 30 seconds

#### 📋 Submit Classification Jobs

**Two Job Types:**
- **Image Classification (MobileNet)**: Uses ImageNet labels (1000 classes)
- **Custom Classification (CLIP)**: Use your own custom labels

**Custom Categories:**
- Save and reuse named label sets (e.g., "Animals", "Vehicles")
- Manage categories in the sidebar
- Quick selection when submitting jobs
- Edit and delete saved categories

**Configuration Options:**
- Top K predictions (1-10)
- Confidence threshold (0.0-1.0)
- Select multiple images per job

#### 📊 Job Status & Results
- Monitor active jobs in real-time
- Auto-refresh option (every 5 seconds)
- View detailed results when completed:
  - Summary metrics (total, classified, unknown)
  - Images grouped by label
  - Detailed results table
  - Processing time and model used

#### 📜 Job History
- View all submitted jobs with filtering:
  - Filter by status (pending, queued, processing, completed, failed)
  - Filter by job type (image_classification, custom_classification)
- Sortable job list
- Click on any job to view details
- See job summary and results
- Auto-refresh every 30 seconds

### Running the Dashboard

```bash
# Using the script (recommended)
./scripts/run-streamlit.sh

# Or manually
cd streamlit-app
export BACKEND_API_URL=$(terraform -chdir=../terraform output -raw alb_endpoint)
streamlit run app.py
```

Access at `http://localhost:8501`

---

## Load Testing

The project includes Locust-based load testing infrastructure for performance and scalability testing.

### Prerequisites

1. **Pre-upload test images:**
```bash
./scripts/pre-upload-images.sh
# or
python3 scripts/pre-upload-images.py --folder images --count 1000
```

2. **Install load test dependencies:**
```bash
cd load-tests
pip3 install -r requirements.txt
```

### Available Test Scenarios

#### 1. Autoscaling Response Test
Tests how quickly autoscaling responds to load spikes.

**Requirements:** Autoscaling **ENABLED**

```bash
./scripts/run-load-test.sh autoscaling_response
```

#### 2. Queue Explosion Test
Tests system behavior when queue depth increases rapidly.

**Requirements:** Autoscaling **ENABLED**

```bash
./scripts/run-load-test.sh queue_explosion
```

#### 3. Sustained Load Test
Tests system stability under sustained load.

**Requirements:** Autoscaling **ENABLED**

```bash
./scripts/run-load-test.sh sustained_load
```

### Run All Tests

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

**Expected Duration:** 30-60 minutes

### Managing Autoscaling

```bash
# Check current autoscaling status
./scripts/manage-autoscaling.sh status

# Suspend autoscaling
./scripts/manage-autoscaling.sh suspend

# Resume autoscaling (for autoscaling tests)
./scripts/manage-autoscaling.sh resume
```

### Generate Reports

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

### Load Test Configuration

Edit `load-tests/config.py` to customize:
- Image count (default: 1000, max: 2000)
- Test parameters (RPS, duration)
- Graph output directory
- Job size distribution

---

## Configuration

### Terraform Variables

Edit `terraform/variables.tf` or create `terraform/terraform.tfvars`:

```hcl
# terraform.tfvars
project_name = "my-classifier"
environment  = "prod"
aws_region   = "us-east-1"

# Backend service configuration
backend_cpu         = 512
backend_memory      = 1024
backend_desired_count = 2

# ML service configuration
ml_cpu         = 2048
ml_memory      = 8192
ml_desired_count = 3
```

### Environment Variables

#### Backend Service
- `PORT`: Server port (default: 8080)
- `AWS_REGION`: AWS region
- `INPUT_BUCKET`: S3 input bucket name
- `OUTPUT_BUCKET`: S3 output bucket name
- `REQUEST_QUEUE_URL`: SQS request queue URL
- `STATUS_QUEUE_URL`: SQS status queue URL
- `DYNAMODB_TABLE`: DynamoDB table name

#### ML Service
- `AWS_REGION`: AWS region
- `REQUEST_QUEUE_URL`: SQS request queue URL
- `STATUS_QUEUE_URL`: SQS status queue URL
- `MAX_WORKERS`: Number of concurrent workers (default: 5)
- `BATCH_SIZE`: Batch size for processing (default: 10)
- `VISIBILITY_TIMEOUT`: SQS visibility timeout in seconds (default: 300)

#### Streamlit App
- `BACKEND_API_URL`: Backend API URL (default: http://localhost:8080)

---

## Monitoring & Logging

### CloudWatch Logs

**View Backend Logs:**
```bash
aws logs tail /ecs/distributed-classifier/backend --follow
```

**View ML Service Logs:**
```bash
aws logs tail /ecs/distributed-classifier/ml-service --follow
```

**Filter Recent Errors:**
```bash
aws logs filter-log-events \
  --log-group-name /ecs/distributed-classifier/backend \
  --filter-pattern "ERROR" \
  --start-time $(date -d '1 hour ago' +%s)000
```

### CloudWatch Metrics

Monitor:
- ECS service metrics (CPU, memory utilization)
- ALB metrics (request count, latency, error rates)
- SQS metrics (queue depth, message age)
- DynamoDB metrics (read/write capacity)

### Health Checks

```bash
# Quick health check
./scripts/health-check.sh

# Manual health check
ALB_ENDPOINT=$(terraform -chdir=terraform output -raw alb_endpoint)
curl $ALB_ENDPOINT/health
```

---

## Development

### Updating Code

When you change the backend or ML service code:

```bash
cd terraform
terraform apply
```

Terraform detects code changes and:
- Rebuilds the affected Docker images
- Pushes to ECR
- Updates ECS task definitions
- Restarts services automatically

### Local Development

**Using Docker Compose (LocalStack):**

```bash
docker-compose up
```

This starts:
- LocalStack (AWS service emulator)
- Backend service (port 8080)
- ML service (port 8000)
- Streamlit app (port 8501)

**Note:** LocalStack provides local AWS services for development without AWS costs.

### Module Details

#### container-registry Module
- **Automatically builds Docker images** when code changes
- Uses `docker_image` and `docker_registry_image` resources
- Triggers rebuilds based on file checksums
- No manual Docker commands needed!

**Key Features:**
- **File change detection**: Rebuilds only when source files change
- **Platform specification**: Builds for `linux/amd64` (ECS compatible)
- **Automatic ECR authentication**: Handled by Terraform provider

### Scaling Services

**Scale Backend Service:**
```bash
./scripts/scale-backend-service.sh 2
```

**Scale ML Service:**
```bash
./scripts/scale-ml-service.sh 5
```

**Check Current Counts:**
```bash
CLUSTER_NAME=$(terraform -chdir=terraform output -raw cluster_name)
BACKEND_SERVICE=$(terraform -chdir=terraform output -raw backend_service_name)

aws ecs describe-services \
  --cluster $CLUSTER_NAME \
  --services $BACKEND_SERVICE \
  --query 'services[0].runningCount' \
  --output text
```

### Testing

**Basic API Tests:**
```bash
./scripts/test-api.sh
```

**End-to-End Tests:**
```bash
./scripts/test-deployment.sh
```

**Health Check:**
```bash
./scripts/health-check.sh
```

---

## Cleanup

### Destroy Infrastructure

```bash
cd terraform
terraform destroy
```

⚠️ **Warning:** This will delete ALL AWS resources including:
- ECS cluster and services
- ECR repositories (and images)
- S3 buckets (and all objects)
- DynamoDB table (and all data)
- SQS queues
- Load balancer
- VPC and networking
- IAM roles and policies
- CloudWatch log groups

### Clean Local Files

```bash
# Remove Terraform state
cd terraform
rm -rf .terraform terraform.tfstate* .terraform.lock.hcl

# Remove Docker images
docker system prune -a

# Remove Python cache
find . -type d -name __pycache__ -exec rm -r {} +
find . -type f -name "*.pyc" -delete
```

---

## Benefits of This Approach

1. **Single Command Deployment**: `terraform apply` does everything
2. **Automatic Change Detection**: Only rebuilds when code changes
3. **Infrastructure as Code**: Everything versioned and reproducible
4. **Modular Design**: Easy to customize individual components
5. **No Manual Steps**: No Docker commands to remember
6. **Scalable Architecture**: Automatic scaling based on load
7. **Cost Effective**: Pay only for what you use
8. **Production Ready**: Includes monitoring, logging, and health checks

---

## Recent Enhancements

### Custom Categories Feature
- Save frequently used label sets as reusable categories
- Quick category selection when submitting custom classification jobs
- Manage categories through the sidebar interface
- Categories stored in session state (persists during app session)

### Job History Feature
- View complete job history with filtering and sorting
- Filter by status and job type
- Interactive job selection to view details
- Access to job results and summaries
- Backend API endpoint: `GET /jobs` with optional query parameters

---

## Next Steps

- [ ] Add API authentication (API keys, OAuth)
- [ ] Set up CI/CD pipeline
- [ ] Configure CloudWatch dashboards
- [ ] Persist custom categories to backend/database
- [ ] Add job export functionality (CSV, JSON)
- [ ] Implement job scheduling
- [ ] Add support for video classification
- [ ] Add model versioning
- [ ] Implement result caching

---

## License

See [LICENSE](LICENSE) file for details.

---

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

---

**No more manual Docker builds!** Just `terraform apply` and deploy. 🎉

**Enhanced UI!** Use the Streamlit interface for a complete image classification workflow. 🖼️

For detailed setup instructions, see [SETUP.md](SETUP.md).
