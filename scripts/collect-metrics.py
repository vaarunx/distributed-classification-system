#!/usr/bin/env python3
"""Collect CloudWatch metrics during load test and extend until queue is empty"""
import sys
import os
import json
import logging
import subprocess
from pathlib import Path
from datetime import datetime

# Add load-tests directory to path
SCRIPT_DIR = Path(__file__).parent
PROJECT_DIR = SCRIPT_DIR.parent
LOAD_TESTS_DIR = PROJECT_DIR / "load-tests"
sys.path.insert(0, str(LOAD_TESTS_DIR))

from utils.metrics_collector import MetricsCollector
from config import AWS_REGION, RESULTS_DIR

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def get_terraform_output(output_name: str) -> str:
    """Get Terraform output value"""
    terraform_dir = PROJECT_DIR / "terraform"
    if not terraform_dir.exists():
        logger.error(f"Terraform directory not found: {terraform_dir}")
        return ""
    
    try:
        result = subprocess.run(
            ["terraform", "output", "-raw", output_name],
            cwd=terraform_dir,
            capture_output=True,
            text=True,
            check=True
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to get Terraform output {output_name}: {e}")
        return ""


def get_queue_url(queue_name: str) -> str:
    """Get SQS queue URL from queue name"""
    import boto3
    sqs = boto3.client("sqs", region_name=AWS_REGION)
    try:
        response = sqs.get_queue_url(QueueName=queue_name)
        return response["QueueUrl"]
    except Exception as e:
        logger.error(f"Failed to get queue URL for {queue_name}: {e}")
        return ""


def main():
    """Main function to collect metrics"""
    if len(sys.argv) < 2:
        logger.error("Usage: collect-metrics.py <test_scenario> [start|stop|extend|check-queue|wait-queue]")
        sys.exit(1)
    
    test_scenario = sys.argv[1]
    action = sys.argv[2] if len(sys.argv) > 2 else "start"
    
    # Get AWS resource names from Terraform
    cluster_name = get_terraform_output("cluster_name")
    backend_service = get_terraform_output("backend_service_name")
    ml_service = get_terraform_output("ml_service_name")
    
    # Get queue name from aws_resources JSON
    terraform_dir = PROJECT_DIR / "terraform"
    queue_name = ""
    try:
        result = subprocess.run(
            ["terraform", "output", "-json", "aws_resources"],
            cwd=terraform_dir,
            capture_output=True,
            text=True,
            check=True
        )
        resources = json.loads(result.stdout)
        queue_name = resources.get("request_queue", "")
    except Exception as e:
        logger.error(f"Failed to get queue name: {e}")
        sys.exit(1)
    
    queue_url = get_queue_url(queue_name)
    if not queue_url:
        logger.error("Failed to get queue URL")
        sys.exit(1)
    
    # Get ALB and target group resource labels for CloudWatch metrics
    load_balancer = get_terraform_output("alb_resource_label")
    target_group = get_terraform_output("target_group_resource_label")
    
    if not load_balancer or not target_group:
        logger.warning("Could not get ALB/target group resource labels. ALB metrics may be incomplete.")
        load_balancer = load_balancer or ""
        target_group = target_group or ""
    
    # Initialize collector
    collector = MetricsCollector(region=AWS_REGION)
    
    # Handle check-queue and wait-queue actions (don't need metrics collection state)
    if action == "check-queue" or action == "wait-queue":
        logger.info("Checking queue status...")
        queue_status = collector.get_queue_attributes(queue_url)
        visible = queue_status['visible']
        in_flight = queue_status['in_flight']
        
        if visible == 0 and in_flight == 0:
            logger.info("✓ Queue is empty. Ready to proceed.")
            sys.exit(0)
        else:
            if action == "check-queue":
                logger.warning(f"Queue not empty: {visible} visible, {in_flight} in-flight.")
                sys.exit(1)
            else:
                # wait-queue: wait for queue to empty
                logger.info(f"Queue not empty: {visible} visible, {in_flight} in-flight. Waiting...")
                # Initialize start_time for extend_collection_until_queue_empty
                collector.start_time = datetime.utcnow()
                success = collector.extend_collection_until_queue_empty(queue_url, poll_interval=30, timeout_seconds=3600)
                if success:
                    logger.info("✓ Queue is now empty. Ready to proceed.")
                    sys.exit(0)
                else:
                    logger.error("Timeout waiting for queue to empty")
                    sys.exit(1)
    
    elif action == "start":
        collector.start_collection()
        logger.info(f"Started metrics collection for {test_scenario}")
        
        # Save collector state (simplified - in production might use a state file)
        state_file = Path(RESULTS_DIR) / f"{test_scenario}_metrics_state.json"
        state_file.parent.mkdir(parents=True, exist_ok=True)
        with open(state_file, "w") as f:
            json.dump({
                "start_time": collector.start_time.isoformat() if collector.start_time else None,
                "test_scenario": test_scenario,
                "cluster_name": cluster_name,
                "backend_service": backend_service,
                "ml_service": ml_service,
                "queue_name": queue_name,
                "queue_url": queue_url
            }, f)
        
    elif action == "extend":
        # Load state
        state_file = Path(RESULTS_DIR) / f"{test_scenario}_metrics_state.json"
        if not state_file.exists():
            logger.error(f"State file not found: {state_file}")
            sys.exit(1)
        
        with open(state_file, "r") as f:
            state = json.load(f)
        
        # Restore collector state
        collector.start_time = datetime.fromisoformat(state["start_time"]) if state.get("start_time") else None
        cluster_name = state.get("cluster_name", cluster_name)
        backend_service = state.get("backend_service", backend_service)
        ml_service = state.get("ml_service", ml_service)
        queue_name = state.get("queue_name", queue_name)
        queue_url = state.get("queue_url", queue_url)
        
        if not collector.start_time:
            logger.error("Collection not started")
            sys.exit(1)
        
        logger.info("Extending metrics collection until queue is empty...")
        collector.extend_collection_until_queue_empty(queue_url, poll_interval=30, timeout_seconds=7200)
        
        # Collect all metrics
        logger.info("Collecting final metrics...")
        collector.collect_all_metrics(
            cluster_name, backend_service, ml_service,
            queue_name, load_balancer, target_group
        )
        
        # Export metrics
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        json_filename = f"{test_scenario}_metrics_{timestamp}.json"
        collector.export_to_json(json_filename)
        logger.info(f"Metrics exported to {json_filename}")
    
    elif action == "stop":
        # Load state and stop collection
        state_file = Path(RESULTS_DIR) / f"{test_scenario}_metrics_state.json"
        if state_file.exists():
            with open(state_file, "r") as f:
                state = json.load(f)
                
                collector.start_time = datetime.fromisoformat(state["start_time"]) if state.get("start_time") else None
                cluster_name = state.get("cluster_name", cluster_name)
                backend_service = state.get("backend_service", backend_service)
                ml_service = state.get("ml_service", ml_service)
                queue_name = state.get("queue_name", queue_name)
                load_balancer = ""
                target_group = ""
        
        collector.stop_collection()
        
        # Collect and export metrics
        collector.collect_all_metrics(
            cluster_name, backend_service, ml_service,
            queue_name, load_balancer, target_group
        )
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        json_filename = f"{test_scenario}_metrics_{timestamp}.json"
        collector.export_to_json(json_filename)
        logger.info(f"Metrics exported to {json_filename}")


if __name__ == "__main__":
    main()

