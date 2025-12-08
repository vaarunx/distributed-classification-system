"""Analyze Locust test results and CloudWatch metrics"""
import json
import csv
import pandas as pd
import logging
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime

import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import RESULTS_DIR

logger = logging.getLogger(__name__)


def parse_locust_csv(csv_file: str) -> pd.DataFrame:
    """Parse Locust CSV results"""
    try:
        df = pd.read_csv(csv_file)
        return df
    except Exception as e:
        logger.error(f"Failed to parse Locust CSV: {str(e)}")
        return pd.DataFrame()


def parse_cloudwatch_json(json_file: str) -> Dict:
    """Parse CloudWatch metrics JSON"""
    try:
        with open(json_file, "r") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Failed to parse CloudWatch JSON: {str(e)}")
        return {}


def calculate_statistics(data: List[float]) -> Dict:
    """Calculate statistics from data"""
    if not data:
        return {}
    
    df = pd.Series(data)
    return {
        "mean": float(df.mean()),
        "median": float(df.median()),
        "min": float(df.min()),
        "max": float(df.max()),
        "p95": float(df.quantile(0.95)),
        "p99": float(df.quantile(0.99)),
        "std": float(df.std()),
        "count": len(data)
    }


def analyze_locust_results(csv_file: str) -> Dict:
    """Analyze Locust test results"""
    df = parse_locust_csv(csv_file)
    
    if df.empty:
        return {}
    
    # Filter for request data
    request_df = df[df["Type"] == "Request"]
    
    results = {
        "total_requests": len(request_df),
        "total_failures": len(request_df[request_df["Failure Count"] > 0]),
        "requests_per_second": float(request_df["Requests/s"].mean()) if "Requests/s" in request_df.columns else 0,
    }
    
    # Response time statistics
    if "Average Response Time" in request_df.columns:
        response_times = request_df["Average Response Time"].dropna().tolist()
        results["response_time"] = calculate_statistics(response_times)
    
    # Min/Max response times
    if "Min Response Time" in request_df.columns:
        results["min_response_time"] = float(request_df["Min Response Time"].min())
    if "Max Response Time" in request_df.columns:
        results["max_response_time"] = float(request_df["Max Response Time"].max())
    
    # Failure rate
    if results["total_requests"] > 0:
        results["failure_rate"] = results["total_failures"] / results["total_requests"]
    else:
        results["failure_rate"] = 0
    
    return results


def analyze_cloudwatch_metrics(json_file: str) -> Dict:
    """Analyze CloudWatch metrics"""
    metrics = parse_cloudwatch_json(json_file)
    
    if not metrics:
        return {}
    
    analysis = {}
    
    for metric_name, datapoints in metrics.items():
        if not datapoints:
            continue
        
        values = [point.get("Average", 0) for point in datapoints]
        analysis[metric_name] = calculate_statistics(values)
    
    return analysis


def generate_summary_report(
    locust_file: Optional[str] = None,
    cloudwatch_file: Optional[str] = None,
    output_file: str = "summary_report.json"
) -> Dict:
    """Generate summary report from all results"""
    report = {
        "timestamp": datetime.utcnow().isoformat(),
        "locust_results": {},
        "cloudwatch_metrics": {},
        "summary": {}
    }
    
    if locust_file:
        report["locust_results"] = analyze_locust_results(locust_file)
    
    if cloudwatch_file:
        report["cloudwatch_metrics"] = analyze_cloudwatch_metrics(cloudwatch_file)
    
    # Generate summary
    summary = {
        "test_completed": True,
        "total_requests": report["locust_results"].get("total_requests", 0),
        "failure_rate": report["locust_results"].get("failure_rate", 0),
        "avg_response_time": report["locust_results"].get("response_time", {}).get("mean", 0),
        "p95_response_time": report["locust_results"].get("response_time", {}).get("p95", 0),
    }
    
    # Add CloudWatch insights
    if "backend_running_tasks" in report["cloudwatch_metrics"]:
        summary["max_backend_tasks"] = report["cloudwatch_metrics"]["backend_running_tasks"].get("max", 0)
    
    if "ml_running_tasks" in report["cloudwatch_metrics"]:
        summary["max_ml_tasks"] = report["cloudwatch_metrics"]["ml_running_tasks"].get("max", 0)
    
    if "sqs_queue_depth" in report["cloudwatch_metrics"]:
        summary["max_queue_depth"] = report["cloudwatch_metrics"]["sqs_queue_depth"].get("max", 0)
    
    report["summary"] = summary
    
    # Save report
    output_path = Path(RESULTS_DIR) / output_file
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, "w") as f:
        json.dump(report, f, indent=2, default=str)
    
    logger.info(f"Generated summary report: {output_path}")
    
    return report


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO)
    
    locust_file = sys.argv[1] if len(sys.argv) > 1 else None
    cloudwatch_file = sys.argv[2] if len(sys.argv) > 2 else None
    
    generate_summary_report(locust_file, cloudwatch_file)

