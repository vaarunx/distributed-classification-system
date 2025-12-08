# Resolving ConcurrentUpdateException in Terraform

## Problem
When running `terraform apply`, you may encounter:
```
ConcurrentUpdateException: You already have a pending update to an Auto Scaling resource.
```

This happens when AWS Application Auto Scaling is processing an update (e.g., scaling actions) while Terraform tries to update the autoscaling target configuration.

## Quick Fix

### Option 1: Wait and Retry (Recommended)
1. Wait 1-2 minutes for any ongoing autoscaling actions to complete
2. Run the wait script:
   ```bash
   ./scripts/wait-for-autoscaling-ready.sh
   ```
3. Retry the deployment:
   ```bash
   terraform apply
   ```

### Option 2: Use the Updated Deploy Script
The `deploy.sh` script now includes automatic retry logic:
```bash
./scripts/deploy.sh
```

It will automatically:
- Detect concurrent update errors
- Wait for autoscaling to stabilize
- Retry up to 3 times

### Option 3: Manual Wait
If the scripts aren't available, simply wait 60-120 seconds and retry:
```bash
sleep 60
terraform apply
```

## Prevention

The Terraform configuration has been updated with lifecycle blocks to handle these situations more gracefully. If you continue to experience frequent conflicts with `role_arn` updates, you can uncomment the `ignore_changes` line in:
- `terraform/modules/ecs-cluster/main.tf` (lines 291 and 292)

This will prevent Terraform from updating the role_arn automatically, allowing you to update it manually when services are stable.

## Understanding the Error

This error typically occurs when:
1. ECS service `desired_count` changes trigger autoscaling actions
2. Terraform tries to update autoscaling target `role_arn` simultaneously
3. AWS blocks the update because autoscaling is already processing changes

The solution is to ensure autoscaling actions complete before updating the autoscaling target configuration.

