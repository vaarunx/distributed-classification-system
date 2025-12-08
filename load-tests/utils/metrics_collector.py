"""CloudWatch metrics collector for load testing"""
import boto3
import json
import csv
import logging
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from pathlib import Path

import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import AWS_REGION, CLOUDWATCH_NAMESPACE, SQS_NAMESPACE, ALB_NAMESPACE, RESULTS_DIR

logger = logging.getLogger(__name__)


class MetricsCollector:
    """Collects CloudWatch metrics during load tests"""
    
    def __init__(self, region: str = AWS_REGION):
        self.cloudwatch = boto3.client("cloudwatch", region_name=region)
        self.sqs = boto3.client("sqs", region_name=region)
        self.metrics: Dict[str, List[Dict]] = {}
        self.start_time: Optional[datetime] = None
        self.end_time: Optional[datetime] = None
    
    def start_collection(self):
        """Start metrics collection"""
        self.start_time = datetime.utcnow()
        self.metrics = {}
        logger.info("Started metrics collection")
    
    def stop_collection(self, end_time: Optional[datetime] = None):
        """Stop metrics collection"""
        if end_time:
            self.end_time = end_time
        else:
            self.end_time = datetime.utcnow()
        logger.info("Stopped metrics collection")
    
    def get_metric_statistics(
        self,
        namespace: str,
        metric_name: str,
        dimensions: List[Dict[str, str]],
        statistic: str = "Average",
        period: int = 60
    ) -> List[Dict]:
        """Get CloudWatch metric statistics"""
        if not self.start_time:
            logger.warning("Collection not started")
            return []
        
        end_time = self.end_time or datetime.utcnow()
        
        try:
            response = self.cloudwatch.get_metric_statistics(
                Namespace=namespace,
                MetricName=metric_name,
                Dimensions=dimensions,
                StartTime=self.start_time - timedelta(minutes=5),
                EndTime=end_time + timedelta(minutes=5),
                Period=period,
                Statistics=[statistic]
            )
            
            return sorted(response["Datapoints"], key=lambda x: x["Timestamp"])
        except Exception as e:
            logger.error(f"Failed to get metric {metric_name}: {str(e)}")
            return []
    
    def collect_ecs_metrics(
        self,
        cluster_name: str,
        service_name: str,
        metric_name: str
    ) -> List[Dict]:
        """Collect ECS service metrics"""
        dimensions = [
            {"Name": "ClusterName", "Value": cluster_name},
            {"Name": "ServiceName", "Value": service_name}
        ]
        return self.get_metric_statistics(CLOUDWATCH_NAMESPACE, metric_name, dimensions)
    
    def collect_sqs_metrics(
        self,
        queue_name: str,
        metric_name: str
    ) -> List[Dict]:
        """Collect SQS queue metrics"""
        dimensions = [{"Name": "QueueName", "Value": queue_name}]
        return self.get_metric_statistics(SQS_NAMESPACE, metric_name, dimensions)
    
    def collect_alb_metrics(
        self,
        load_balancer: str,
        target_group: str,
        metric_name: str
    ) -> List[Dict]:
        """Collect ALB metrics"""
        dimensions = [
            {"Name": "LoadBalancer", "Value": load_balancer},
            {"Name": "TargetGroup", "Value": target_group}
        ]
        return self.get_metric_statistics(ALB_NAMESPACE, metric_name, dimensions)
    
    def collect_all_metrics(
        self,
        cluster_name: str,
        backend_service: str,
        ml_service: str,
        queue_name: str,
        load_balancer: str,
        target_group: str
    ):
        """Collect all relevant metrics"""
        logger.info("Collecting CloudWatch metrics...")
        
        # ECS metrics
        self.metrics["backend_cpu"] = self.collect_ecs_metrics(
            cluster_name, backend_service, "CPUUtilization"
        )
        self.metrics["backend_memory"] = self.collect_ecs_metrics(
            cluster_name, backend_service, "MemoryUtilization"
        )
        self.metrics["backend_running_tasks"] = self.collect_ecs_metrics(
            cluster_name, backend_service, "RunningTaskCount"
        )
        
        self.metrics["ml_cpu"] = self.collect_ecs_metrics(
            cluster_name, ml_service, "CPUUtilization"
        )
        self.metrics["ml_memory"] = self.collect_ecs_metrics(
            cluster_name, ml_service, "MemoryUtilization"
        )
        self.metrics["ml_running_tasks"] = self.collect_ecs_metrics(
            cluster_name, ml_service, "RunningTaskCount"
        )
        
        # SQS metrics
        self.metrics["sqs_queue_depth"] = self.collect_sqs_metrics(
            queue_name, "ApproximateNumberOfMessagesVisible"
        )
        self.metrics["sqs_in_flight"] = self.collect_sqs_metrics(
            queue_name, "ApproximateNumberOfMessagesNotVisible"
        )
        
        # ALB metrics
        self.metrics["alb_request_count"] = self.collect_alb_metrics(
            load_balancer, target_group, "RequestCount"
        )
        self.metrics["alb_response_time"] = self.collect_alb_metrics(
            load_balancer, target_group, "TargetResponseTime"
        )
        self.metrics["alb_http_5xx"] = self.collect_alb_metrics(
            load_balancer, target_group, "HTTPCode_Target_5XX_Count"
        )
        
        logger.info("Metrics collection complete")
    
    def export_to_csv(self, filename: str):
        """Export metrics to CSV"""
        output_path = Path(RESULTS_DIR) / filename
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["Metric", "Timestamp", "Value"])
            
            for metric_name, datapoints in self.metrics.items():
                for point in datapoints:
                    writer.writerow([
                        metric_name,
                        point["Timestamp"].isoformat(),
                        point["Average"]
                    ])
        
        logger.info(f"Exported metrics to {output_path}")
    
    def export_to_json(self, filename: str):
        """Export metrics to JSON"""
        output_path = Path(RESULTS_DIR) / filename
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, "w") as f:
            json.dump(self.metrics, f, indent=2, default=str)
        
        logger.info(f"Exported metrics to {output_path}")
    
    def get_queue_attributes(self, queue_url: str) -> Dict[str, int]:
        """Get SQS queue attributes for visible and in-flight messages"""
        try:
            response = self.sqs.get_queue_attributes(
                QueueUrl=queue_url,
                AttributeNames=['ApproximateNumberOfMessages', 'ApproximateNumberOfMessagesNotVisible']
            )
            attributes = response.get('Attributes', {})
            return {
                'visible': int(attributes.get('ApproximateNumberOfMessages', 0)),
                'in_flight': int(attributes.get('ApproximateNumberOfMessagesNotVisible', 0))
            }
        except Exception as e:
            logger.error(f"Failed to get queue attributes: {str(e)}")
            return {'visible': 0, 'in_flight': 0}
    
    def extend_collection_until_queue_empty(
        self,
        queue_url: str,
        poll_interval: int = 30,
        timeout_seconds: int = 7200
    ) -> bool:
        """Extend metrics collection until SQS queue is empty"""
        if not self.start_time:
            logger.warning("Collection not started, cannot extend")
            return False
        
        start_wait = datetime.utcnow()
        timeout_time = start_wait + timedelta(seconds=timeout_seconds)
        
        logger.info("Extending metrics collection until queue is empty...")
        
        while datetime.utcnow() < timeout_time:
            queue_status = self.get_queue_attributes(queue_url)
            visible = queue_status['visible']
            in_flight = queue_status['in_flight']
            
            # Update end_time to current time to extend collection window
            self.end_time = datetime.utcnow()
            
            if visible == 0 and in_flight == 0:
                logger.info("Queue is empty. Stopping metrics collection.")
                return True
            
            logger.info(f"Queue: {visible} visible, {in_flight} in-flight. Continuing metrics collection...")
            time.sleep(poll_interval)
        
        logger.warning(f"Timeout reached ({timeout_seconds}s) while waiting for queue to empty")
        return False
    
    def collect_metrics_until_queue_empty(
        self,
        cluster_name: str,
        backend_service: str,
        ml_service: str,
        queue_url: str,
        queue_name: str,
        load_balancer: str,
        target_group: str,
        poll_interval: int = 30,
        timeout_seconds: int = 7200
    ):
        """Collect all metrics and extend collection until queue is empty"""
        # Collect metrics with current end_time
        self.collect_all_metrics(
            cluster_name, backend_service, ml_service,
            queue_name, load_balancer, target_group
        )
        
        # Extend collection until queue is empty
        self.extend_collection_until_queue_empty(queue_url, poll_interval, timeout_seconds)
        
        # Collect final metrics with updated end_time
        self.collect_all_metrics(
            cluster_name, backend_service, ml_service,
            queue_name, load_balancer, target_group
        )

