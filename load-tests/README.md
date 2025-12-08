# Load Testing Infrastructure

This directory contains Locust-based load testing infrastructure for the distributed classification system.

## Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Configure environment variables:
```bash
# Copy the example file
cp .env.example .env

# Edit .env with your values
# Key variables to set:
# - BACKEND_API_URL: Your ALB endpoint (get from: terraform output alb_endpoint)
# - IMAGE_FOLDER: Path to images folder (default: ../images)
# - IMAGE_COUNT: Number of images to upload (default: 1000)
# - AWS_REGION: AWS region (default: us-east-1)
# - AWS credentials: Optional if using IAM roles or ~/.aws/credentials
```

## Pre-upload Images

Before running tests, upload images to S3:

```bash
# Using Python script (recommended)
python3 ../scripts/pre-upload-images.py --folder ../images --count 1000

# Or using shell script
../scripts/pre-upload-images.sh
```

This will:
- Upload images from the `images/` folder to S3
- Generate `s3_keys.json` mapping file
- Support resume from checkpoint if interrupted

## Running Tests

### Managing Autoscaling

Some tests require autoscaling to be disabled/enabled. Use the autoscaling management script:

```bash
# Check current autoscaling status
../scripts/manage-autoscaling.sh status

# Suspend autoscaling (for throughput_scaling test)
../scripts/manage-autoscaling.sh suspend

# Resume autoscaling (for autoscaling tests)
../scripts/manage-autoscaling.sh resume
```

### Single Test

```bash
../scripts/run-load-test.sh throughput_scaling
```

Available test scenarios:
- `throughput_scaling` - Throughput scaling curve test (requires autoscaling **DISABLED**)
- `autoscaling_response` - Autoscaling response time test (requires autoscaling **ENABLED**)
- `queue_explosion` - Queue depth explosion test (requires autoscaling **ENABLED**)
- `sustained_load` - Sustained load stability test (requires autoscaling **ENABLED**)

**Important**: Before running `throughput_scaling`, suspend autoscaling:
```bash
../scripts/manage-autoscaling.sh suspend
../scripts/run-load-test.sh throughput_scaling
```

### All Tests

```bash
../scripts/run-all-tests.sh
```

This runs all tests sequentially with automatic autoscaling management:
1. Suspends autoscaling for `throughput_scaling`
2. Resumes autoscaling for remaining tests
3. Generates a consolidated report at the end

## Generating Reports and Graphs

After running tests, generate graphs and analysis:

```bash
../scripts/generate-report.sh
```

This will:
- Generate all graphs (PNG format)
- Create summary report (JSON)
- Save everything to `reports/` directory

## Graph Types

The following graphs are generated:
1. **Throughput vs Task Count** - Request count and task count over time
2. **Latency over Time** - Response time with p50, p95, p99
3. **Autoscaling Response** - Task count changes over time for both services
4. **Queue Depth over Time** - SQS queue depth visualization
5. **Request Rate over Time** - Request count over time
6. **Error Rate over Time** - 5xx errors over time
7. **Resource Utilization** - CPU and memory for both services

## Configuration

Edit `config.py` to customize:
- Image count (default: 1000, max: 2000)
- Test parameters (RPS, duration)
- Graph output directory
- Job size distribution

## Results

Test results are saved to:
- `results/` - Locust CSV results and HTML reports
- `reports/` - Generated graphs and analysis reports

