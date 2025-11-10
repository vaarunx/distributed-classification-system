# Distributed Image Classifier - Simplified Deployment

A serverless image classification system with **automatic Docker builds** handled by Terraform.

## ✨ Key Improvement

**No manual Docker commands needed!** Terraform now:
- Builds Docker images automatically
- Pushes to ECR
- Deploys everything in one command

## 📁 New Module Structure

```
terraform/
├── main.tf              # Root configuration
├── variables.tf         # Configuration options
├── outputs.tf          # Output values
└── modules/
    ├── container-registry/  # Handles Docker builds & ECR
    ├── networking/         # VPC, Security Groups
    ├── storage/           # S3, DynamoDB
    ├── queues/            # SQS
    ├── iam/               # Roles and Policies
    ├── load-balancer/     # ALB
    └── ecs-cluster/       # ECS Services
```

## 🚀 Quick Start

### Prerequisites

1. AWS CLI configured
2. Terraform installed (>= 1.0)
3. Docker daemon running locally

### Deploy Everything

```bash
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
terraform output alb_endpoint
```

## 🔄 Updating Code

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

## 📊 Testing the API

```bash
# Get the ALB endpoint
ALB_ENDPOINT=$(terraform -chdir=terraform output -raw alb_endpoint)

# Submit a classification job
curl -X POST ${ALB_ENDPOINT}/submit \
  -H "Content-Type: application/json" \
  -d '{
    "job_type": "image_classification",
    "s3_keys": ["test/image.jpg"],
    "top_k": 5,
    "confidence_threshold": 0.5
  }'

# Check status
curl ${ALB_ENDPOINT}/status/{job-id}

# Get results
curl ${ALB_ENDPOINT}/result/{job-id}
```

## 🔧 Configuration

Edit `terraform/variables.tf` or create `terraform/terraform.tfvars`:

```hcl
# terraform.tfvars
project_name = "my-classifier"
environment  = "prod"
backend_cpu  = 512
backend_memory = 1024
ml_cpu = 2048
ml_memory = 8192
backend_desired_count = 2
ml_desired_count = 3
```

## 📝 Module Details

### container-registry Module
- **Automatically builds Docker images** when code changes
- Uses `docker_image` and `docker_registry_image` resources
- Triggers rebuilds based on file checksums
- No manual Docker commands needed!

### Key Features
- **File change detection**: Rebuilds only when source files change
- **Platform specification**: Builds for `linux/amd64` (ECS compatible)
- **Automatic ECR authentication**: Handled by Terraform provider

## 🧹 Cleanup

```bash
cd terraform
terraform destroy
```

## 💡 Benefits of This Approach

1. **Single Command Deployment**: `terraform apply` does everything
2. **Automatic Change Detection**: Only rebuilds when code changes
3. **Infrastructure as Code**: Everything versioned and reproducible
4. **Modular Design**: Easy to customize individual components
5. **No Manual Steps**: No Docker commands to remember

## 🔍 Monitoring

View logs:
```bash
# Backend logs
aws logs tail /ecs/distributed-classifier/backend --follow

# ML service logs
aws logs tail /ecs/distributed-classifier/ml-service --follow
```

## 🎯 What Happens During `terraform apply`

1. **Checks for code changes** in backend-service/ and ml-service/
2. **Builds Docker images** if changes detected
3. **Pushes to ECR** automatically
4. **Updates infrastructure** if needed
5. **Deploys new task definitions** with updated images
6. **Restarts ECS services** to use new images

## 🚨 Troubleshooting

If Docker build fails:
- Ensure Docker daemon is running
- Check Docker has enough disk space
- Verify AWS credentials are configured

If ECS services won't start:
- Check CloudWatch logs
- Verify security groups allow traffic
- Ensure task roles have correct permissions

## 📚 Next Steps

- Add auto-scaling policies
- Implement API authentication
- Set up CI/CD pipeline
- Configure monitoring dashboards

---

**No more manual Docker builds!** Just `terraform apply` and deploy. 🎉