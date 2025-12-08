"""Generate enhanced graphs from test results and CloudWatch metrics"""
import json
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import seaborn as sns
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from scipy import stats
from scipy.interpolate import interp1d

import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import GRAPH_OUTPUT_DIR, RESULTS_DIR

logger = logging.getLogger(__name__)

# Set professional style
sns.set_style("whitegrid")
sns.set_palette("husl")
plt.rcParams["figure.figsize"] = (14, 10)
plt.rcParams["font.size"] = 10
plt.rcParams["axes.labelsize"] = 11
plt.rcParams["axes.titlesize"] = 13
plt.rcParams["xtick.labelsize"] = 9
plt.rcParams["ytick.labelsize"] = 9
plt.rcParams["legend.fontsize"] = 9
plt.rcParams["figure.dpi"] = 300


# ============================================================================
# Helper Functions
# ============================================================================

def load_cloudwatch_metrics(json_file: str) -> Dict:
    """Load CloudWatch metrics from JSON"""
    try:
        with open(json_file, "r") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Failed to load CloudWatch metrics: {str(e)}")
        return {}


def load_locust_csv(csv_file: str) -> pd.DataFrame:
    """Load Locust CSV results"""
    try:
        return pd.read_csv(csv_file)
    except Exception as e:
        logger.error(f"Failed to load Locust CSV: {str(e)}")
        return pd.DataFrame()


def load_locust_stats_history(csv_file: str) -> pd.DataFrame:
    """Load Locust stats_history.csv for time-series data"""
    try:
        # Try to find stats_history file
        csv_path = Path(csv_file)
        if "_stats_history" not in csv_path.name:
            # Try to find corresponding stats_history file
            base_name = csv_path.stem.replace("_stats", "")
            stats_history_path = csv_path.parent / f"{base_name}_stats_history.csv"
            if stats_history_path.exists():
                df = pd.read_csv(stats_history_path)
                # Convert Unix timestamp to datetime
                if "Timestamp" in df.columns:
                    df["datetime"] = pd.to_datetime(df["Timestamp"], unit="s")
                return df
        else:
            df = pd.read_csv(csv_file)
            if "Timestamp" in df.columns:
                df["datetime"] = pd.to_datetime(df["Timestamp"], unit="s")
            return df
    except Exception as e:
        logger.warning(f"Failed to load Locust stats_history: {str(e)}")
        return pd.DataFrame()


def align_timestamps(locust_df: pd.DataFrame, metrics: Dict) -> Tuple[pd.DataFrame, Dict]:
    """Align timestamps between Locust and CloudWatch data"""
    if locust_df.empty or not metrics:
        return locust_df, metrics
    
    # Get time range from Locust data
    if "datetime" in locust_df.columns:
        locust_start = locust_df["datetime"].min()
        locust_end = locust_df["datetime"].max()
    else:
        return locust_df, metrics
    
    # Align CloudWatch timestamps to Locust timezone
    aligned_metrics = {}
    for metric_name, datapoints in metrics.items():
        if not datapoints:
            aligned_metrics[metric_name] = []
            continue
        
        aligned_points = []
        for point in datapoints:
            timestamp = pd.to_datetime(point["Timestamp"])
            # Only include points within Locust time range
            if locust_start <= timestamp <= locust_end:
                aligned_points.append(point)
        
        aligned_metrics[metric_name] = aligned_points
    
    return locust_df, aligned_metrics


def interpolate_cloudwatch_data(metrics: Dict, target_timestamps: pd.Series) -> Dict:
    """Interpolate sparse CloudWatch data to match target timestamps"""
    interpolated = {}
    
    for metric_name, datapoints in metrics.items():
        if not datapoints or len(datapoints) < 2:
            interpolated[metric_name] = datapoints
            continue
        
        timestamps = pd.to_datetime([p["Timestamp"] for p in datapoints])
        values = [p["Average"] for p in datapoints]
        
        # Create interpolation function
        try:
            interp_func = interp1d(
                timestamps.astype(np.int64),
                values,
                kind="linear",
                bounds_error=False,
                fill_value="extrapolate"
            )
            
            # Interpolate to target timestamps
            interpolated_values = interp_func(target_timestamps.astype(np.int64))
            
            interpolated[metric_name] = [
                {"Timestamp": ts, "Average": float(val)}
                for ts, val in zip(target_timestamps, interpolated_values)
            ]
        except Exception as e:
            logger.warning(f"Failed to interpolate {metric_name}: {str(e)}")
            interpolated[metric_name] = datapoints
    
    return interpolated


def normalize_timestamp(ts):
    """Normalize timestamp to timezone-naive datetime"""
    if isinstance(ts, pd.Series):
        ts = pd.to_datetime(ts)
        if ts.dt.tz is not None:
            ts = ts.dt.tz_localize(None)
        return ts
    else:
        ts = pd.to_datetime(ts)
        if hasattr(ts, 'tz') and ts.tz is not None:
            ts = ts.tz_localize(None)
        return ts


def calculate_correlation(x: pd.Series, y: pd.Series) -> float:
    """Calculate Pearson correlation coefficient"""
    try:
        # Align series
        aligned = pd.DataFrame({"x": x, "y": y}).dropna()
        if len(aligned) < 2:
            return 0.0
        return float(stats.pearsonr(aligned["x"], aligned["y"])[0])
    except Exception:
        return 0.0


def add_test_metadata(fig, test_name: Optional[str] = None, test_date: Optional[str] = None):
    """Add test metadata to figure (only if test_name is provided)"""
    # Skip metadata for consolidated metric-focused graphs
    if test_name:
        metadata_text = []
        if test_name:
            metadata_text.append(f"Test: {test_name}")
        if test_date:
            metadata_text.append(f"Date: {test_date}")
        
        if metadata_text:
            fig.text(0.99, 0.01, " | ".join(metadata_text), 
                    ha="right", va="bottom", fontsize=8, alpha=0.7)


def detect_scaling_events(task_data: List[Dict]) -> List[Tuple[datetime, str, float]]:
    """Detect scaling events (scale up/down) from task count data"""
    if len(task_data) < 2:
        return []
    
    events = []
    prev_value = task_data[0]["Average"]
    
    for point in task_data[1:]:
        current_value = point["Average"]
        timestamp = pd.to_datetime(point["Timestamp"])
        
        if current_value > prev_value:
            events.append((timestamp, "scale_up", current_value - prev_value))
        elif current_value < prev_value:
            events.append((timestamp, "scale_down", prev_value - current_value))
        
        prev_value = current_value
    
    return events


# ============================================================================
# Enhanced Existing Graphs
# ============================================================================

def plot_throughput_vs_task_count(
    metrics: Dict,
    locust_df: Optional[pd.DataFrame] = None,
    output_file: str = "throughput_vs_tasks.png",
    test_name: Optional[str] = None
):
    """Plot enhanced throughput vs task count with correlations"""
    if "backend_running_tasks" not in metrics or "alb_request_count" not in metrics:
        logger.warning("Missing data for throughput vs task count")
        return
    
    fig, ax1 = plt.subplots(figsize=(14, 8))
    
    # Get request data
    request_data = metrics.get("alb_request_count", [])
    backend_tasks = metrics.get("backend_running_tasks", [])
    ml_tasks = metrics.get("ml_running_tasks", [])
    
    if not request_data or not backend_tasks:
        logger.warning("Insufficient data for throughput vs task count")
        plt.close()
        return
    
    # Convert to DataFrames for easier manipulation
    req_df = pd.DataFrame(request_data)
    req_df["Timestamp"] = pd.to_datetime(req_df["Timestamp"])
    
    backend_df = pd.DataFrame(backend_tasks)
    backend_df["Timestamp"] = pd.to_datetime(backend_df["Timestamp"])
    
    # Plot request count
    ax1.plot(req_df["Timestamp"], req_df["Average"], "b-", linewidth=2, 
             label="Request Count", alpha=0.8)
    ax1.fill_between(req_df["Timestamp"], req_df["Average"], alpha=0.3, color="blue")
    ax1.set_xlabel("Time", fontsize=11)
    ax1.set_ylabel("Request Count", color="b", fontsize=11)
    ax1.tick_params(axis="y", labelcolor="b")
    ax1.grid(True, alpha=0.3)
    
    # Plot backend tasks on secondary axis
    ax2 = ax1.twinx()
    ax2.plot(backend_df["Timestamp"], backend_df["Average"], "r-", linewidth=2,
             label="Backend Tasks", marker="o", markersize=3)
    
    # Plot ML tasks if available
    if ml_tasks:
        ml_df = pd.DataFrame(ml_tasks)
        ml_df["Timestamp"] = pd.to_datetime(ml_df["Timestamp"])
        ax2.plot(ml_df["Timestamp"], ml_df["Average"], "g-", linewidth=2,
                 label="ML Tasks", marker="s", markersize=3)
    
    ax2.set_ylabel("Task Count", color="r", fontsize=11)
    ax2.tick_params(axis="y", labelcolor="r")
    
    # Add statistical annotations
    if len(req_df) > 0 and len(backend_df) > 0:
        max_req = req_df["Average"].max()
        max_tasks = backend_df["Average"].max()
        mean_req = req_df["Average"].mean()
        mean_tasks = backend_df["Average"].mean()
        
        ax1.text(0.02, 0.98, f"Max Requests: {max_req:.1f}\nMean Requests: {mean_req:.1f}",
                transform=ax1.transAxes, fontsize=9, verticalalignment="top",
                bbox=dict(boxstyle="round", facecolor="wheat", alpha=0.5))
        
        ax2.text(0.98, 0.98, f"Max Tasks: {max_tasks:.1f}\nMean Tasks: {mean_tasks:.1f}",
                transform=ax2.transAxes, fontsize=9, verticalalignment="top", ha="right",
                bbox=dict(boxstyle="round", facecolor="lightcoral", alpha=0.5))
    
    # Add scaling event markers
    scaling_events = detect_scaling_events(backend_tasks)
    for event_time, event_type, delta in scaling_events[:10]:  # Limit to first 10
        color = "green" if event_type == "scale_up" else "red"
        ax2.axvline(x=event_time, color=color, linestyle="--", alpha=0.5, linewidth=1)
    
    ax1.set_title("Throughput vs Task Count (Backend & ML Services)", fontsize=13, fontweight="bold")
    ax1.legend(loc="upper left")
    ax2.legend(loc="upper right")
    
    plt.xticks(rotation=45)
    plt.tight_layout()
    add_test_metadata(fig, test_name)
    
    output_path = Path(GRAPH_OUTPUT_DIR) / output_file
    output_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(output_path, dpi=300, bbox_inches="tight")
    plt.close()
    logger.info(f"Saved graph: {output_path}")


def plot_latency_over_time(
    locust_df: pd.DataFrame,
    locust_stats_history: pd.DataFrame = None,
    metrics: Dict = None,
    output_file: str = "latency_over_time.png",
    test_name: Optional[str] = None
):
    """Plot enhanced latency over time with multiple percentiles and failure rate"""
    # Try to use stats_history if available
    if locust_stats_history is not None and not locust_stats_history.empty:
        df = locust_stats_history
        time_col = "datetime" if "datetime" in df.columns else "Timestamp"
    elif not locust_df.empty:
        df = locust_df[locust_df["Type"] == "Request"] if "Type" in locust_df.columns else locust_df
        time_col = None
    else:
        logger.warning("No Locust data for latency plot")
        return
    
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 10), sharex=True)
    
    # Determine time axis
    if time_col and time_col in df.columns:
        timestamps = df[time_col]
        use_datetime = True
    else:
        timestamps = range(len(df))
        use_datetime = False
    
    # Plot percentiles
    percentile_cols = {
        "50%": ("50th", "blue", "-", 2),
        "75%": ("75th", "cyan", "-", 1.5),
        "90%": ("90th", "yellow", "--", 1.5),
        "95%": ("95th", "orange", "--", 2),
        "99%": ("99th", "red", ":", 2),
        "99.9%": ("99.9th", "purple", ":", 1.5)
    }
    
    plotted_percentiles = []
    for col, (label, color, linestyle, lw) in percentile_cols.items():
        if col in df.columns:
            ax1.plot(timestamps, df[col], label=label, color=color, 
                    linestyle=linestyle, linewidth=lw, alpha=0.8)
            plotted_percentiles.append(col)
    
    # Plot average if available
    if "Total Average Response Time" in df.columns:
        ax1.plot(timestamps, df["Total Average Response Time"], 
                label="Average", color="black", linewidth=2.5, alpha=0.9)
    elif "Average Response Time" in df.columns:
        ax1.plot(timestamps, df["Average Response Time"], 
                label="Average", color="black", linewidth=2.5, alpha=0.9)
    
    # Add min/max bands if available
    if "Total Min Response Time" in df.columns and "Total Max Response Time" in df.columns:
        ax1.fill_between(timestamps, df["Total Min Response Time"], 
                        df["Total Max Response Time"], alpha=0.2, color="gray", 
                        label="Min-Max Range")
    
    ax1.set_ylabel("Response Time (ms)", fontsize=11)
    ax1.set_title("Latency over Time - Percentiles", fontsize=13, fontweight="bold")
    ax1.legend(loc="upper left", ncol=4)
    ax1.grid(True, alpha=0.3)
    
    # Plot failure rate on second subplot
    if "Failures/s" in df.columns:
        ax2.plot(timestamps, df["Failures/s"], label="Failures/s", 
                color="red", linewidth=2, marker="x", markersize=4)
        ax2.set_ylabel("Failures per Second", fontsize=11, color="red")
        ax2.tick_params(axis="y", labelcolor="red")
        ax2.legend(loc="upper left")
        ax2.grid(True, alpha=0.3)
    elif "Total Failure Count" in df.columns:
        # Calculate failure rate if we have cumulative failure count
        if len(df) > 1:
            failure_rate = df["Total Failure Count"].diff().fillna(0)
            ax2.plot(timestamps, failure_rate, label="Failures", 
                    color="red", linewidth=2, marker="x", markersize=4)
            ax2.set_ylabel("Failures", fontsize=11, color="red")
            ax2.tick_params(axis="y", labelcolor="red")
            ax2.legend(loc="upper left")
            ax2.grid(True, alpha=0.3)
    
    if use_datetime:
        ax2.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M:%S"))
        plt.xticks(rotation=45)
    else:
        ax2.set_xlabel("Time (sample)", fontsize=11)
    
    plt.tight_layout()
    add_test_metadata(fig, test_name)
    
    output_path = Path(GRAPH_OUTPUT_DIR) / output_file
    output_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(output_path, dpi=300, bbox_inches="tight")
    plt.close()
    logger.info(f"Saved graph: {output_path}")


def plot_autoscaling_response(
    metrics: Dict,
    output_file: str = "autoscaling_response.png",
    test_name: Optional[str] = None
):
    """Plot enhanced autoscaling response with both services and queue correlation"""
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 10), sharex=True)
    
    backend_tasks = metrics.get("backend_running_tasks", [])
    ml_tasks = metrics.get("ml_running_tasks", [])
    queue_depth = metrics.get("sqs_queue_depth", [])
    
    if not backend_tasks and not ml_tasks:
        logger.warning("Missing task data for autoscaling plot")
        plt.close()
        return
    
    # Plot backend tasks
    if backend_tasks:
        backend_df = pd.DataFrame(backend_tasks)
        backend_df["Timestamp"] = pd.to_datetime(backend_df["Timestamp"])
        
        ax1.plot(backend_df["Timestamp"], backend_df["Average"], "b-", 
                linewidth=2.5, marker="o", markersize=4, label="Backend Tasks", alpha=0.9)
        ax1.fill_between(backend_df["Timestamp"], backend_df["Average"], alpha=0.3, color="blue")
        
        # Add scaling event markers
        events = detect_scaling_events(backend_tasks)
        for event_time, event_type, delta in events[:15]:
            color = "green" if event_type == "scale_up" else "red"
            ax1.axvline(x=event_time, color=color, linestyle="--", alpha=0.6, linewidth=1.5)
            if event_type == "scale_up":
                ax1.text(event_time, ax1.get_ylim()[1] * 0.9, f"+{int(delta)}", 
                        rotation=90, ha="right", fontsize=8, color=color)
        
        # Add queue depth overlay on secondary axis
        if queue_depth:
            ax1_queue = ax1.twinx()
            queue_df = pd.DataFrame(queue_depth)
            queue_df["Timestamp"] = pd.to_datetime(queue_df["Timestamp"])
            ax1_queue.plot(queue_df["Timestamp"], queue_df["Average"], 
                          "g--", linewidth=1.5, alpha=0.6, label="Queue Depth")
            ax1_queue.set_ylabel("Queue Depth", color="g", fontsize=10)
            ax1_queue.tick_params(axis="y", labelcolor="g")
            ax1_queue.legend(loc="upper right")
        
        ax1.set_ylabel("Backend Task Count", fontsize=11, color="b")
        ax1.tick_params(axis="y", labelcolor="b")
        ax1.set_title("Backend Service Autoscaling (with Queue Depth)", fontsize=12, fontweight="bold")
        ax1.legend(loc="upper left")
        ax1.grid(True, alpha=0.3)
    
    # Plot ML tasks
    if ml_tasks:
        ml_df = pd.DataFrame(ml_tasks)
        ml_df["Timestamp"] = pd.to_datetime(ml_df["Timestamp"])
        
        ax2.plot(ml_df["Timestamp"], ml_df["Average"], "r-", 
                linewidth=2.5, marker="s", markersize=4, label="ML Tasks", alpha=0.9)
        ax2.fill_between(ml_df["Timestamp"], ml_df["Average"], alpha=0.3, color="red")
        
        # Add scaling event markers
        events = detect_scaling_events(ml_tasks)
        for event_time, event_type, delta in events[:15]:
            color = "green" if event_type == "scale_up" else "orange"
            ax2.axvline(x=event_time, color=color, linestyle="--", alpha=0.6, linewidth=1.5)
            if event_type == "scale_up":
                ax2.text(event_time, ax2.get_ylim()[1] * 0.9, f"+{int(delta)}", 
                        rotation=90, ha="right", fontsize=8, color=color)
        
        ax2.set_ylabel("ML Service Task Count", fontsize=11, color="r")
        ax2.set_xlabel("Time", fontsize=11)
        ax2.tick_params(axis="y", labelcolor="r")
        ax2.set_title("ML Service Autoscaling", fontsize=12, fontweight="bold")
        ax2.legend(loc="upper left")
        ax2.grid(True, alpha=0.3)
    
    plt.xticks(rotation=45)
    plt.tight_layout()
    add_test_metadata(fig, test_name)
    
    output_path = Path(GRAPH_OUTPUT_DIR) / output_file
    output_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(output_path, dpi=300, bbox_inches="tight")
    plt.close()
    logger.info(f"Saved graph: {output_path}")


def plot_queue_depth_over_time(
    metrics: Dict,
    output_file: str = "queue_depth_over_time.png",
    test_name: Optional[str] = None
):
    """Plot enhanced queue depth with in-flight messages and task correlation"""
    if "sqs_queue_depth" not in metrics:
        logger.warning("Missing queue depth data")
        return
    
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 10), sharex=True)
    
    queue_data = metrics.get("sqs_queue_depth", [])
    in_flight = metrics.get("sqs_in_flight", [])
    ml_tasks = metrics.get("ml_running_tasks", [])
    
    if not queue_data:
        logger.warning("No queue depth data available")
        plt.close()
        return
    
    queue_df = pd.DataFrame(queue_data)
    queue_df["Timestamp"] = pd.to_datetime(queue_df["Timestamp"])
    
    # Plot queue depth
    ax1.plot(queue_df["Timestamp"], queue_df["Average"], "g-", 
            linewidth=2.5, marker="o", markersize=3, label="Queue Depth", alpha=0.9)
    ax1.fill_between(queue_df["Timestamp"], queue_df["Average"], alpha=0.3, color="green")
    
    # Add in-flight messages if available
    if in_flight:
        in_flight_df = pd.DataFrame(in_flight)
        in_flight_df["Timestamp"] = pd.to_datetime(in_flight_df["Timestamp"])
        ax1.plot(in_flight_df["Timestamp"], in_flight_df["Average"], "orange", 
                linewidth=2, linestyle="--", marker="s", markersize=3, 
                label="In-Flight Messages", alpha=0.8)
    
    # Add ML task count overlay
    if ml_tasks:
        ax1_tasks = ax1.twinx()
        ml_df = pd.DataFrame(ml_tasks)
        ml_df["Timestamp"] = pd.to_datetime(ml_df["Timestamp"])
        ax1_tasks.plot(ml_df["Timestamp"], ml_df["Average"], "r-", 
                      linewidth=1.5, alpha=0.6, label="ML Tasks")
        ax1_tasks.set_ylabel("ML Task Count", color="r", fontsize=10)
        ax1_tasks.tick_params(axis="y", labelcolor="r")
        ax1_tasks.legend(loc="upper right")
    
    ax1.set_ylabel("Queue Depth (messages)", fontsize=11, color="g")
    ax1.tick_params(axis="y", labelcolor="g")
    ax1.set_title("SQS Queue Depth and In-Flight Messages", fontsize=12, fontweight="bold")
    ax1.legend(loc="upper left")
    ax1.grid(True, alpha=0.3)
    
    # Calculate and plot queue processing rate
    if len(queue_df) > 1:
        queue_df_sorted = queue_df.sort_values("Timestamp")
        time_diffs = queue_df_sorted["Timestamp"].diff().dt.total_seconds()
        depth_diffs = queue_df_sorted["Average"].diff()
        processing_rate = -(depth_diffs / time_diffs).fillna(0)  # Negative because depth decreases
        
        ax2.plot(queue_df_sorted["Timestamp"], processing_rate, "purple", 
                linewidth=2, marker="o", markersize=3, label="Processing Rate (msg/s)", alpha=0.8)
        ax2.axhline(y=0, color="black", linestyle="-", linewidth=0.5, alpha=0.5)
        ax2.fill_between(queue_df_sorted["Timestamp"], processing_rate, 0, 
                        where=(processing_rate >= 0), alpha=0.3, color="green", label="Processing")
        ax2.fill_between(queue_df_sorted["Timestamp"], processing_rate, 0, 
                        where=(processing_rate < 0), alpha=0.3, color="red", label="Buildup")
    
    ax2.set_ylabel("Queue Processing Rate (messages/sec)", fontsize=11)
    ax2.set_xlabel("Time", fontsize=11)
    ax2.set_title("Queue Processing Rate", fontsize=12, fontweight="bold")
    ax2.legend(loc="upper left")
    ax2.grid(True, alpha=0.3)
    
    # Add statistics
    if len(queue_df) > 0:
        max_depth = queue_df["Average"].max()
        mean_depth = queue_df["Average"].mean()
        ax1.text(0.02, 0.98, f"Max Depth: {max_depth:.0f}\nMean Depth: {mean_depth:.1f}",
                transform=ax1.transAxes, fontsize=9, verticalalignment="top",
                bbox=dict(boxstyle="round", facecolor="lightgreen", alpha=0.7))
    
    plt.xticks(rotation=45)
    plt.tight_layout()
    add_test_metadata(fig, test_name)
    
    output_path = Path(GRAPH_OUTPUT_DIR) / output_file
    output_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(output_path, dpi=300, bbox_inches="tight")
    plt.close()
    logger.info(f"Saved graph: {output_path}")


def plot_request_rate_over_time(
    metrics: Dict,
    locust_stats_history: pd.DataFrame = None,
    output_file: str = "request_rate_over_time.png",
    test_name: Optional[str] = None
):
    """Plot enhanced request rate with user count and cumulative requests"""
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 10), sharex=True)
    
    # Use Locust stats_history if available (more accurate RPS)
    if locust_stats_history is not None and not locust_stats_history.empty:
        df = locust_stats_history
        time_col = "datetime" if "datetime" in df.columns else "Timestamp"
        
        if "Requests/s" in df.columns:
            timestamps = df[time_col] if time_col in df.columns else range(len(df))
            ax1.plot(timestamps, df["Requests/s"], "purple", linewidth=2.5, 
                    marker="o", markersize=3, label="Requests per Second", alpha=0.9)
            
            # Add moving average
            if len(df) > 5:
                window = min(10, len(df) // 5)
                moving_avg = df["Requests/s"].rolling(window=window, center=True).mean()
                ax1.plot(timestamps, moving_avg, "orange", linewidth=2, 
                        linestyle="--", label=f"Moving Avg ({window}s)", alpha=0.7)
            
            # Add user count overlay
            if "User Count" in df.columns:
                ax1_users = ax1.twinx()
                ax1_users.plot(timestamps, df["User Count"], "cyan", 
                              linewidth=1.5, linestyle=":", alpha=0.6, label="User Count")
                ax1_users.set_ylabel("User Count", color="cyan", fontsize=10)
                ax1_users.tick_params(axis="y", labelcolor="cyan")
                ax1_users.legend(loc="upper right")
            
            ax1.set_ylabel("Requests per Second", fontsize=11, color="purple")
            ax1.tick_params(axis="y", labelcolor="purple")
            
            # Plot cumulative requests
            if "Total Request Count" in df.columns:
                ax2.plot(timestamps, df["Total Request Count"], "blue", 
                        linewidth=2.5, label="Cumulative Requests", alpha=0.9)
                ax2.fill_between(timestamps, df["Total Request Count"], alpha=0.3, color="blue")
                ax2.set_ylabel("Total Requests", fontsize=11)
                ax2.set_title("Cumulative Request Count", fontsize=12, fontweight="bold")
                ax2.legend(loc="upper left")
                ax2.grid(True, alpha=0.3)
    else:
        # Fallback to CloudWatch ALB metrics
        request_data = metrics.get("alb_request_count", [])
        if not request_data:
            logger.warning("Missing request count data")
            plt.close()
            return
        
        req_df = pd.DataFrame(request_data)
        req_df["Timestamp"] = pd.to_datetime(req_df["Timestamp"])
        
        ax1.plot(req_df["Timestamp"], req_df["Average"], "purple", 
                linewidth=2.5, marker="o", markersize=3, label="Request Count", alpha=0.9)
        ax1.set_ylabel("Request Count", fontsize=11, color="purple")
        ax1.tick_params(axis="y", labelcolor="purple")
    
    ax1.set_title("Request Rate over Time", fontsize=12, fontweight="bold")
    ax1.legend(loc="upper left")
    ax1.grid(True, alpha=0.3)
    
    if "Total Request Count" not in (locust_stats_history.columns if locust_stats_history is not None and not locust_stats_history.empty else []):
        ax2.set_xlabel("Time", fontsize=11)
        ax2.axis("off")
    
    plt.xticks(rotation=45)
    plt.tight_layout()
    add_test_metadata(fig, test_name)
    
    output_path = Path(GRAPH_OUTPUT_DIR) / output_file
    output_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(output_path, dpi=300, bbox_inches="tight")
    plt.close()
    logger.info(f"Saved graph: {output_path}")


def plot_error_rate_over_time(
    metrics: Dict,
    locust_stats_history: pd.DataFrame = None,
    output_file: str = "error_rate_over_time.png",
    test_name: Optional[str] = None
):
    """Plot enhanced error rate with 4xx/5xx breakdown and percentage"""
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 10), sharex=True)
    
    # Try to get 4xx errors if available
    error_4xx = metrics.get("alb_http_4xx", [])
    error_5xx = metrics.get("alb_http_5xx", [])
    
    # Also check Locust data for failure rate
    locust_failures = None
    if locust_stats_history is not None and not locust_stats_history.empty:
        if "Failures/s" in locust_stats_history.columns:
            locust_failures = locust_stats_history
            time_col = "datetime" if "datetime" in locust_stats_history.columns else "Timestamp"
    
    if not error_5xx and not error_4xx and locust_failures is None:
        logger.warning("Missing error data")
        plt.close()
        return
    
    # Plot error counts
    if error_5xx:
        error_5xx_df = pd.DataFrame(error_5xx)
        error_5xx_df["Timestamp"] = pd.to_datetime(error_5xx_df["Timestamp"])
        ax1.plot(error_5xx_df["Timestamp"], error_5xx_df["Average"], "r-", 
                linewidth=2.5, marker="x", markersize=5, label="5xx Errors", alpha=0.9)
        ax1.fill_between(error_5xx_df["Timestamp"], error_5xx_df["Average"], 
                        alpha=0.3, color="red")
    
    if error_4xx:
        error_4xx_df = pd.DataFrame(error_4xx)
        error_4xx_df["Timestamp"] = pd.to_datetime(error_4xx_df["Timestamp"])
        ax1.plot(error_4xx_df["Timestamp"], error_4xx_df["Average"], "orange", 
                linewidth=2, marker="s", markersize=4, label="4xx Errors", alpha=0.8)
        ax1.fill_between(error_4xx_df["Timestamp"], error_4xx_df["Average"], 
                        alpha=0.2, color="orange")
    
    if locust_failures is not None:
        timestamps = locust_failures[time_col] if time_col in locust_failures.columns else range(len(locust_failures))
        ax1.plot(timestamps, locust_failures["Failures/s"], "purple", 
                linewidth=2, linestyle="--", marker="o", markersize=3, 
                label="Locust Failures/s", alpha=0.7)
    
    ax1.set_ylabel("Error Count", fontsize=11)
    ax1.set_title("Error Rate over Time (4xx and 5xx)", fontsize=12, fontweight="bold")
    ax1.legend(loc="upper left")
    ax1.grid(True, alpha=0.3)
    
    # Calculate and plot error percentage if we have request count
    request_data = metrics.get("alb_request_count", [])
    if request_data and error_5xx:
        req_df = pd.DataFrame(request_data)
        req_df["Timestamp"] = pd.to_datetime(req_df["Timestamp"])
        error_5xx_df = pd.DataFrame(error_5xx)
        error_5xx_df["Timestamp"] = pd.to_datetime(error_5xx_df["Timestamp"])
        
        # Merge on timestamp
        merged = pd.merge_asof(req_df.sort_values("Timestamp"), 
                               error_5xx_df.sort_values("Timestamp"),
                               on="Timestamp", suffixes=("_req", "_err"))
        
        if len(merged) > 0 and merged["Average_req"].sum() > 0:
            error_pct = (merged["Average_err"] / merged["Average_req"] * 100).fillna(0)
            ax2.plot(merged["Timestamp"], error_pct, "red", 
                    linewidth=2.5, marker="x", markersize=5, label="Error Percentage", alpha=0.9)
            ax2.fill_between(merged["Timestamp"], error_pct, alpha=0.3, color="red")
            ax2.axhline(y=1.0, color="orange", linestyle="--", linewidth=1.5, 
                       alpha=0.7, label="1% Threshold")
            ax2.axhline(y=5.0, color="red", linestyle="--", linewidth=1.5, 
                       alpha=0.7, label="5% Threshold")
    
    ax2.set_ylabel("Error Percentage (%)", fontsize=11)
    ax2.set_xlabel("Time", fontsize=11)
    ax2.set_title("Error Percentage over Time", fontsize=12, fontweight="bold")
    ax2.legend(loc="upper left")
    ax2.grid(True, alpha=0.3)
    
    plt.xticks(rotation=45)
    plt.tight_layout()
    add_test_metadata(fig, test_name)
    
    output_path = Path(GRAPH_OUTPUT_DIR) / output_file
    output_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(output_path, dpi=300, bbox_inches="tight")
    plt.close()
    logger.info(f"Saved graph: {output_path}")


def plot_resource_utilization(
    metrics: Dict,
    output_file: str = "resource_utilization.png",
    test_name: Optional[str] = None
):
    """Plot enhanced resource utilization with CPU/memory combined and task overlay"""
    fig, axes = plt.subplots(2, 2, figsize=(16, 12))
    
    # Backend CPU and Memory
    backend_cpu = metrics.get("backend_cpu", [])
    backend_memory = metrics.get("backend_memory", [])
    backend_tasks = metrics.get("backend_running_tasks", [])
    
    if backend_cpu:
        cpu_df = pd.DataFrame(backend_cpu)
        cpu_df["Timestamp"] = pd.to_datetime(cpu_df["Timestamp"])
        
        ax = axes[0, 0]
        ax.plot(cpu_df["Timestamp"], cpu_df["Average"], "b-", 
               linewidth=2.5, label="CPU", alpha=0.9)
        ax.fill_between(cpu_df["Timestamp"], cpu_df["Average"], alpha=0.3, color="blue")
        ax.axhline(y=80, color="red", linestyle="--", linewidth=1.5, 
                  alpha=0.7, label="80% Threshold")
        
        # Add task count overlay
        if backend_tasks:
            ax_tasks = ax.twinx()
            tasks_df = pd.DataFrame(backend_tasks)
            tasks_df["Timestamp"] = pd.to_datetime(tasks_df["Timestamp"])
            ax_tasks.plot(tasks_df["Timestamp"], tasks_df["Average"], "gray", 
                         linewidth=1.5, linestyle=":", alpha=0.6, label="Tasks")
            ax_tasks.set_ylabel("Task Count", color="gray", fontsize=9)
            ax_tasks.tick_params(axis="y", labelcolor="gray", labelsize=8)
            ax_tasks.legend(loc="upper right", fontsize=8)
        
        ax.set_ylabel("CPU Utilization (%)", fontsize=11, color="b")
        ax.tick_params(axis="y", labelcolor="b")
        ax.set_title("Backend CPU Utilization", fontsize=12, fontweight="bold")
        ax.legend(loc="upper left")
        ax.grid(True, alpha=0.3)
    
    if backend_memory:
        mem_df = pd.DataFrame(backend_memory)
        mem_df["Timestamp"] = pd.to_datetime(mem_df["Timestamp"])
        
        ax = axes[0, 1]
        ax.plot(mem_df["Timestamp"], mem_df["Average"], "cyan", 
               linewidth=2.5, label="Memory", alpha=0.9)
        ax.fill_between(mem_df["Timestamp"], mem_df["Average"], alpha=0.3, color="cyan")
        ax.axhline(y=80, color="red", linestyle="--", linewidth=1.5, 
                  alpha=0.7, label="80% Threshold")
        
        if backend_tasks:
            ax_tasks = ax.twinx()
            tasks_df = pd.DataFrame(backend_tasks)
            tasks_df["Timestamp"] = pd.to_datetime(tasks_df["Timestamp"])
            ax_tasks.plot(tasks_df["Timestamp"], tasks_df["Average"], "gray", 
                         linewidth=1.5, linestyle=":", alpha=0.6, label="Tasks")
            ax_tasks.set_ylabel("Task Count", color="gray", fontsize=9)
            ax_tasks.tick_params(axis="y", labelcolor="gray", labelsize=8)
            ax_tasks.legend(loc="upper right", fontsize=8)
        
        ax.set_ylabel("Memory Utilization (%)", fontsize=11, color="cyan")
        ax.tick_params(axis="y", labelcolor="cyan")
        ax.set_title("Backend Memory Utilization", fontsize=12, fontweight="bold")
        ax.legend(loc="upper left")
        ax.grid(True, alpha=0.3)
    
    # ML CPU and Memory
    ml_cpu = metrics.get("ml_cpu", [])
    ml_memory = metrics.get("ml_memory", [])
    ml_tasks = metrics.get("ml_running_tasks", [])
    
    if ml_cpu:
        cpu_df = pd.DataFrame(ml_cpu)
        cpu_df["Timestamp"] = pd.to_datetime(cpu_df["Timestamp"])
        
        ax = axes[1, 0]
        ax.plot(cpu_df["Timestamp"], cpu_df["Average"], "r-", 
               linewidth=2.5, label="CPU", alpha=0.9)
        ax.fill_between(cpu_df["Timestamp"], cpu_df["Average"], alpha=0.3, color="red")
        ax.axhline(y=80, color="red", linestyle="--", linewidth=1.5, 
                  alpha=0.7, label="80% Threshold")
        
        if ml_tasks:
            ax_tasks = ax.twinx()
            tasks_df = pd.DataFrame(ml_tasks)
            tasks_df["Timestamp"] = pd.to_datetime(tasks_df["Timestamp"])
            ax_tasks.plot(tasks_df["Timestamp"], tasks_df["Average"], "gray", 
                         linewidth=1.5, linestyle=":", alpha=0.6, label="Tasks")
            ax_tasks.set_ylabel("Task Count", color="gray", fontsize=9)
            ax_tasks.tick_params(axis="y", labelcolor="gray", labelsize=8)
            ax_tasks.legend(loc="upper right", fontsize=8)
        
        ax.set_ylabel("CPU Utilization (%)", fontsize=11, color="r")
        ax.set_xlabel("Time", fontsize=11)
        ax.tick_params(axis="y", labelcolor="r")
        ax.set_title("ML Service CPU Utilization", fontsize=12, fontweight="bold")
        ax.legend(loc="upper left")
        ax.grid(True, alpha=0.3)
    
    if ml_memory:
        mem_df = pd.DataFrame(ml_memory)
        mem_df["Timestamp"] = pd.to_datetime(mem_df["Timestamp"])
        
        ax = axes[1, 1]
        ax.plot(mem_df["Timestamp"], mem_df["Average"], "pink", 
               linewidth=2.5, label="Memory", alpha=0.9)
        ax.fill_between(mem_df["Timestamp"], mem_df["Average"], alpha=0.3, color="pink")
        ax.axhline(y=80, color="red", linestyle="--", linewidth=1.5, 
                  alpha=0.7, label="80% Threshold")
        
        if ml_tasks:
            ax_tasks = ax.twinx()
            tasks_df = pd.DataFrame(ml_tasks)
            tasks_df["Timestamp"] = pd.to_datetime(tasks_df["Timestamp"])
            ax_tasks.plot(tasks_df["Timestamp"], tasks_df["Average"], "gray", 
                         linewidth=1.5, linestyle=":", alpha=0.6, label="Tasks")
            ax_tasks.set_ylabel("Task Count", color="gray", fontsize=9)
            ax_tasks.tick_params(axis="y", labelcolor="gray", labelsize=8)
            ax_tasks.legend(loc="upper right", fontsize=8)
        
        ax.set_ylabel("Memory Utilization (%)", fontsize=11, color="pink")
        ax.set_xlabel("Time", fontsize=11)
        ax.tick_params(axis="y", labelcolor="pink")
        ax.set_title("ML Service Memory Utilization", fontsize=12, fontweight="bold")
        ax.legend(loc="upper left")
        ax.grid(True, alpha=0.3)
    
    plt.xticks(rotation=45)
    plt.tight_layout()
    add_test_metadata(fig, test_name)
    
    output_path = Path(GRAPH_OUTPUT_DIR) / output_file
    output_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(output_path, dpi=300, bbox_inches="tight")
    plt.close()
    logger.info(f"Saved graph: {output_path}")


# ============================================================================
# New Detailed Analysis Graphs
# ============================================================================

def plot_system_correlation_dashboard(
    metrics: Dict,
    locust_stats_history: pd.DataFrame = None,
    output_file: str = "system_correlation_dashboard.png",
    test_name: Optional[str] = None
):
    """Plot system correlation dashboard with multiple correlation views"""
    fig, axes = plt.subplots(2, 2, figsize=(16, 12))
    
    # Prepare data
    queue_depth = metrics.get("sqs_queue_depth", [])
    backend_tasks = metrics.get("backend_running_tasks", [])
    ml_tasks = metrics.get("ml_running_tasks", [])
    request_count = metrics.get("alb_request_count", [])
    backend_cpu = metrics.get("backend_cpu", [])
    
    # 1. Queue Depth vs Task Count
    if queue_depth and ml_tasks:
        queue_df = pd.DataFrame(queue_depth)
        queue_df["Timestamp"] = normalize_timestamp(queue_df["Timestamp"])
        tasks_df = pd.DataFrame(ml_tasks)
        tasks_df["Timestamp"] = normalize_timestamp(tasks_df["Timestamp"])
        
        merged = pd.merge_asof(queue_df.sort_values("Timestamp"), 
                               tasks_df.sort_values("Timestamp"),
                               on="Timestamp", suffixes=("_queue", "_tasks"))
        
        if len(merged) > 0:
            ax = axes[0, 0]
            scatter = ax.scatter(merged["Average_tasks"], merged["Average_queue"], 
                               c=range(len(merged)), cmap="viridis", 
                               s=50, alpha=0.6, edgecolors="black", linewidth=0.5)
            ax.set_xlabel("ML Task Count", fontsize=11)
            ax.set_ylabel("Queue Depth", fontsize=11)
            ax.set_title("Queue Depth vs Task Count", fontsize=12, fontweight="bold")
            ax.grid(True, alpha=0.3)
            
            # Calculate correlation
            corr = calculate_correlation(merged["Average_tasks"], merged["Average_queue"])
            ax.text(0.05, 0.95, f"Correlation: {corr:.3f}", 
                   transform=ax.transAxes, fontsize=10, verticalalignment="top",
                   bbox=dict(boxstyle="round", facecolor="wheat", alpha=0.7))
    
    # 2. Latency vs CPU
    if locust_stats_history is not None and not locust_stats_history.empty and backend_cpu:
        lat_df = locust_stats_history.copy()
        cpu_df = pd.DataFrame(backend_cpu)
        cpu_df["Timestamp"] = normalize_timestamp(cpu_df["Timestamp"])
        
        time_col = "datetime" if "datetime" in lat_df.columns else "Timestamp"
        if time_col in lat_df.columns:
            lat_df["Timestamp"] = normalize_timestamp(lat_df[time_col])
            merged = pd.merge_asof(lat_df.sort_values("Timestamp"), 
                                   cpu_df.sort_values("Timestamp"),
                                   on="Timestamp", suffixes=("_lat", "_cpu"))
            
            if len(merged) > 0:
                # Find the correct column names
                cpu_col = None
                lat_col = None
                for col in merged.columns:
                    if "Average" in col and "cpu" in col.lower():
                        cpu_col = col
                    elif "Total Average Response Time" in col or ("Average" in col and "Response" in col):
                        lat_col = col
                
                if cpu_col and lat_col:
                    ax = axes[0, 1]
                    scatter = ax.scatter(merged[cpu_col], merged[lat_col],
                                        c=range(len(merged)), cmap="coolwarm", 
                                        s=50, alpha=0.6, edgecolors="black", linewidth=0.5)
                    ax.set_xlabel("Backend CPU (%)", fontsize=11)
                    ax.set_ylabel("Response Time (ms)", fontsize=11)
                    ax.set_title("Latency vs CPU Utilization", fontsize=12, fontweight="bold")
                    ax.grid(True, alpha=0.3)
                    
                    corr = calculate_correlation(merged[cpu_col], merged[lat_col])
                    ax.text(0.05, 0.95, f"Correlation: {corr:.3f}", 
                           transform=ax.transAxes, fontsize=10, verticalalignment="top",
                           bbox=dict(boxstyle="round", facecolor="wheat", alpha=0.7))
    
    # 3. Request Rate vs Queue Depth
    if request_count and queue_depth:
        req_df = pd.DataFrame(request_count)
        req_df["Timestamp"] = normalize_timestamp(req_df["Timestamp"])
        queue_df = pd.DataFrame(queue_depth)
        queue_df["Timestamp"] = normalize_timestamp(queue_df["Timestamp"])
        
        merged = pd.merge_asof(req_df.sort_values("Timestamp"), 
                               queue_df.sort_values("Timestamp"),
                               on="Timestamp", suffixes=("_req", "_queue"))
        
        if len(merged) > 0:
            ax = axes[1, 0]
            scatter = ax.scatter(merged["Average_req"], merged["Average_queue"],
                               c=range(len(merged)), cmap="plasma", 
                               s=50, alpha=0.6, edgecolors="black", linewidth=0.5)
            ax.set_xlabel("Request Count", fontsize=11)
            ax.set_ylabel("Queue Depth", fontsize=11)
            ax.set_title("Request Rate vs Queue Depth", fontsize=12, fontweight="bold")
            ax.grid(True, alpha=0.3)
            
            corr = calculate_correlation(merged["Average_req"], merged["Average_queue"])
            ax.text(0.05, 0.95, f"Correlation: {corr:.3f}", 
                   transform=ax.transAxes, fontsize=10, verticalalignment="top",
                   bbox=dict(boxstyle="round", facecolor="wheat", alpha=0.7))
    
    # 4. Task Count Comparison (Backend vs ML)
    if backend_tasks and ml_tasks:
        backend_df = pd.DataFrame(backend_tasks)
        backend_df["Timestamp"] = normalize_timestamp(backend_df["Timestamp"])
        ml_df = pd.DataFrame(ml_tasks)
        ml_df["Timestamp"] = normalize_timestamp(ml_df["Timestamp"])
        
        merged = pd.merge_asof(backend_df.sort_values("Timestamp"), 
                               ml_df.sort_values("Timestamp"),
                               on="Timestamp", suffixes=("_backend", "_ml"))
        
        if len(merged) > 0:
            ax = axes[1, 1]
            scatter = ax.scatter(merged["Average_backend"], merged["Average_ml"],
                               c=range(len(merged)), cmap="Set2", 
                               s=50, alpha=0.6, edgecolors="black", linewidth=0.5)
            ax.set_xlabel("Backend Task Count", fontsize=11)
            ax.set_ylabel("ML Task Count", fontsize=11)
            ax.set_title("Backend vs ML Task Count", fontsize=12, fontweight="bold")
            ax.grid(True, alpha=0.3)
            
            corr = calculate_correlation(merged["Average_backend"], merged["Average_ml"])
            ax.text(0.05, 0.95, f"Correlation: {corr:.3f}", 
                   transform=ax.transAxes, fontsize=10, verticalalignment="top",
                   bbox=dict(boxstyle="round", facecolor="wheat", alpha=0.7))
    
    plt.tight_layout()
    add_test_metadata(fig, test_name)
    
    output_path = Path(GRAPH_OUTPUT_DIR) / output_file
    output_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(output_path, dpi=300, bbox_inches="tight")
    plt.close()
    logger.info(f"Saved graph: {output_path}")


def plot_latency_distribution(
    locust_stats_history: pd.DataFrame = None,
    output_file: str = "latency_distribution.png",
    test_name: Optional[str] = None
):
    """Plot latency distribution with histogram, box plots, and CDF"""
    if locust_stats_history is None or locust_stats_history.empty:
        logger.warning("No Locust stats_history data for latency distribution")
        return
    
    fig, axes = plt.subplots(2, 2, figsize=(16, 12))
    
    # Get response time data
    if "Total Average Response Time" in locust_stats_history.columns:
        response_times = locust_stats_history["Total Average Response Time"].dropna()
    elif "Average Response Time" in locust_stats_history.columns:
        response_times = locust_stats_history["Average Response Time"].dropna()
    else:
        logger.warning("No response time data available")
        plt.close()
        return
    
    if len(response_times) == 0:
        logger.warning("Empty response time data")
        plt.close()
        return
    
    # 1. Histogram
    ax = axes[0, 0]
    ax.hist(response_times, bins=50, color="skyblue", edgecolor="black", alpha=0.7)
    ax.axvline(response_times.mean(), color="red", linestyle="--", 
               linewidth=2, label=f"Mean: {response_times.mean():.1f}ms")
    ax.axvline(response_times.median(), color="green", linestyle="--", 
               linewidth=2, label=f"Median: {response_times.median():.1f}ms")
    ax.set_xlabel("Response Time (ms)", fontsize=11)
    ax.set_ylabel("Frequency", fontsize=11)
    ax.set_title("Response Time Distribution", fontsize=12, fontweight="bold")
    ax.legend()
    ax.grid(True, alpha=0.3)
    
    # 2. Box Plot by time period
    ax = axes[0, 1]
    # Divide into time periods
    n_periods = min(10, len(response_times) // 10)
    if n_periods > 1:
        period_size = len(response_times) // n_periods
        periods = []
        period_labels = []
        for i in range(n_periods):
            start_idx = i * period_size
            end_idx = (i + 1) * period_size if i < n_periods - 1 else len(response_times)
            periods.append(response_times.iloc[start_idx:end_idx].values)
            period_labels.append(f"T{i+1}")
        
        bp = ax.boxplot(periods, labels=period_labels, patch_artist=True)
        for patch in bp["boxes"]:
            patch.set_facecolor("lightblue")
            patch.set_alpha(0.7)
        ax.set_xlabel("Time Period", fontsize=11)
        ax.set_ylabel("Response Time (ms)", fontsize=11)
        ax.set_title("Response Time by Time Period", fontsize=12, fontweight="bold")
        ax.grid(True, alpha=0.3, axis="y")
    
    # 3. Cumulative Distribution Function (CDF)
    ax = axes[1, 0]
    sorted_times = np.sort(response_times)
    p = np.arange(1, len(sorted_times) + 1) / len(sorted_times)
    ax.plot(sorted_times, p * 100, linewidth=2.5, color="purple")
    ax.axvline(response_times.quantile(0.95), color="red", linestyle="--", 
              linewidth=1.5, label="P95")
    ax.axvline(response_times.quantile(0.99), color="orange", linestyle="--", 
              linewidth=1.5, label="P99")
    ax.set_xlabel("Response Time (ms)", fontsize=11)
    ax.set_ylabel("Cumulative Probability (%)", fontsize=11)
    ax.set_title("Cumulative Distribution Function", fontsize=12, fontweight="bold")
    ax.legend()
    ax.grid(True, alpha=0.3)
    
    # 4. Percentile heatmap over time
    ax = axes[1, 1]
    if "datetime" in locust_stats_history.columns or "Timestamp" in locust_stats_history.columns:
        time_col = "datetime" if "datetime" in locust_stats_history.columns else "Timestamp"
        percentiles = ["50%", "75%", "90%", "95%", "99%"]
        available_percentiles = [p for p in percentiles if p in locust_stats_history.columns]
        
        if available_percentiles:
            # Sample data for heatmap (take every nth point)
            sample_size = min(50, len(locust_stats_history))
            step = max(1, len(locust_stats_history) // sample_size)
            sampled = locust_stats_history.iloc[::step]
            
            heatmap_data = []
            for p in available_percentiles:
                heatmap_data.append(sampled[p].values)
            
            if heatmap_data:
                im = ax.imshow(heatmap_data, aspect="auto", cmap="YlOrRd", interpolation="nearest")
                ax.set_yticks(range(len(available_percentiles)))
                ax.set_yticklabels(available_percentiles)
                ax.set_xlabel("Time Sample", fontsize=11)
                ax.set_ylabel("Percentile", fontsize=11)
                ax.set_title("Percentile Heatmap over Time", fontsize=12, fontweight="bold")
                plt.colorbar(im, ax=ax, label="Response Time (ms)")
    
    plt.tight_layout()
    add_test_metadata(fig, test_name)
    
    output_path = Path(GRAPH_OUTPUT_DIR) / output_file
    output_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(output_path, dpi=300, bbox_inches="tight")
    plt.close()
    logger.info(f"Saved graph: {output_path}")


def plot_throughput_analysis(
    metrics: Dict,
    locust_stats_history: pd.DataFrame = None,
    output_file: str = "throughput_analysis.png",
    test_name: Optional[str] = None
):
    """Plot throughput analysis with efficiency metrics"""
    fig, axes = plt.subplots(2, 2, figsize=(16, 12))
    
    # 1. Requests per second with moving average
    if locust_stats_history is not None and not locust_stats_history.empty:
        if "Requests/s" in locust_stats_history.columns:
            time_col = "datetime" if "datetime" in locust_stats_history.columns else "Timestamp"
            timestamps = locust_stats_history[time_col] if time_col in locust_stats_history.columns else range(len(locust_stats_history))
            
            ax = axes[0, 0]
            ax.plot(timestamps, locust_stats_history["Requests/s"], 
                   "blue", linewidth=2, alpha=0.7, label="RPS")
            
            # Moving average
            window = min(10, len(locust_stats_history) // 5)
            if window > 1:
                moving_avg = locust_stats_history["Requests/s"].rolling(window=window, center=True).mean()
                ax.plot(timestamps, moving_avg, "red", linewidth=2.5, 
                       linestyle="--", label=f"Moving Avg ({window}s)")
            
            ax.set_xlabel("Time", fontsize=11)
            ax.set_ylabel("Requests per Second", fontsize=11)
            ax.set_title("Request Rate over Time", fontsize=12, fontweight="bold")
            ax.legend()
            ax.grid(True, alpha=0.3)
    
    # 2. Throughput efficiency (requests per task)
    request_count = metrics.get("alb_request_count", [])
    backend_tasks = metrics.get("backend_running_tasks", [])
    
    if request_count and backend_tasks:
        req_df = pd.DataFrame(request_count)
        req_df["Timestamp"] = pd.to_datetime(req_df["Timestamp"])
        tasks_df = pd.DataFrame(backend_tasks)
        tasks_df["Timestamp"] = pd.to_datetime(tasks_df["Timestamp"])
        
        merged = pd.merge_asof(req_df.sort_values("Timestamp"), 
                               tasks_df.sort_values("Timestamp"),
                               on="Timestamp", suffixes=("_req", "_tasks"))
        
        if len(merged) > 0:
            # Calculate requests per task (avoid division by zero)
            efficiency = merged["Average_req"] / merged["Average_tasks"].replace(0, np.nan)
            
            ax = axes[0, 1]
            ax.plot(merged["Timestamp"], efficiency, "green", 
                   linewidth=2.5, marker="o", markersize=3, alpha=0.8)
            ax.fill_between(merged["Timestamp"], efficiency, alpha=0.3, color="green")
            ax.set_xlabel("Time", fontsize=11)
            ax.set_ylabel("Requests per Task", fontsize=11)
            ax.set_title("Throughput Efficiency", fontsize=12, fontweight="bold")
            ax.grid(True, alpha=0.3)
    
    # 3. Job completion rate (if we can estimate from queue processing)
    queue_depth = metrics.get("sqs_queue_depth", [])
    if queue_depth and len(queue_depth) > 1:
        queue_df = pd.DataFrame(queue_depth)
        queue_df["Timestamp"] = pd.to_datetime(queue_df["Timestamp"])
        queue_df_sorted = queue_df.sort_values("Timestamp")
        
        time_diffs = queue_df_sorted["Timestamp"].diff().dt.total_seconds()
        depth_diffs = queue_df_sorted["Average"].diff()
        processing_rate = -(depth_diffs / time_diffs).fillna(0)
        processing_rate = processing_rate.clip(lower=0)  # Only positive rates
        
        ax = axes[1, 0]
        ax.plot(queue_df_sorted["Timestamp"], processing_rate, "purple", 
               linewidth=2.5, marker="o", markersize=3, alpha=0.8)
        ax.fill_between(queue_df_sorted["Timestamp"], processing_rate, alpha=0.3, color="purple")
        ax.set_xlabel("Time", fontsize=11)
        ax.set_ylabel("Processing Rate (jobs/sec)", fontsize=11)
        ax.set_title("Job Processing Rate", fontsize=12, fontweight="bold")
        ax.grid(True, alpha=0.3)
    
    # 4. Backlog processing rate
    if queue_depth and len(queue_depth) > 1:
        queue_df = pd.DataFrame(queue_depth)
        queue_df["Timestamp"] = pd.to_datetime(queue_df["Timestamp"])
        
        ax = axes[1, 1]
        ax.plot(queue_df["Timestamp"], queue_df["Average"], "orange", 
               linewidth=2.5, marker="s", markersize=3, alpha=0.8, label="Queue Depth")
        ax.fill_between(queue_df["Timestamp"], queue_df["Average"], alpha=0.3, color="orange")
        
        # Add trend line
        if len(queue_df) > 5:
            z = np.polyfit(range(len(queue_df)), queue_df["Average"], 1)
            p = np.poly1d(z)
            ax.plot(queue_df["Timestamp"], p(range(len(queue_df))), 
                   "red", linestyle="--", linewidth=2, label="Trend")
        
        ax.set_xlabel("Time", fontsize=11)
        ax.set_ylabel("Queue Depth (messages)", fontsize=11)
        ax.set_title("Backlog Processing", fontsize=12, fontweight="bold")
        ax.legend()
        ax.grid(True, alpha=0.3)
    
    plt.xticks(rotation=45)
    plt.tight_layout()
    add_test_metadata(fig, test_name)
    
    output_path = Path(GRAPH_OUTPUT_DIR) / output_file
    output_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(output_path, dpi=300, bbox_inches="tight")
    plt.close()
    logger.info(f"Saved graph: {output_path}")


def plot_scaling_efficiency(
    metrics: Dict,
    locust_stats_history: pd.DataFrame = None,
    output_file: str = "scaling_efficiency.png",
    test_name: Optional[str] = None
):
    """Plot scaling efficiency metrics"""
    fig, axes = plt.subplots(2, 2, figsize=(16, 12))
    
    backend_tasks = metrics.get("backend_running_tasks", [])
    ml_tasks = metrics.get("ml_running_tasks", [])
    request_count = metrics.get("alb_request_count", [])
    
    # 1. Task count vs throughput ratio
    if backend_tasks and request_count:
        tasks_df = pd.DataFrame(backend_tasks)
        tasks_df["Timestamp"] = pd.to_datetime(tasks_df["Timestamp"])
        req_df = pd.DataFrame(request_count)
        req_df["Timestamp"] = pd.to_datetime(req_df["Timestamp"])
        
        merged = pd.merge_asof(tasks_df.sort_values("Timestamp"), 
                               req_df.sort_values("Timestamp"),
                               on="Timestamp", suffixes=("_tasks", "_req"))
        
        if len(merged) > 0:
            ratio = merged["Average_req"] / merged["Average_tasks"].replace(0, np.nan)
            
            ax = axes[0, 0]
            ax.plot(merged["Timestamp"], ratio, "blue", 
                   linewidth=2.5, marker="o", markersize=3, alpha=0.8)
            ax.fill_between(merged["Timestamp"], ratio, alpha=0.3, color="blue")
            ax.set_xlabel("Time", fontsize=11)
            ax.set_ylabel("Requests per Task", fontsize=11)
            ax.set_title("Task Efficiency (Requests per Task)", fontsize=12, fontweight="bold")
            ax.grid(True, alpha=0.3)
    
    # 2. Scaling lag analysis
    if ml_tasks and request_count:
        tasks_df = pd.DataFrame(ml_tasks)
        tasks_df["Timestamp"] = pd.to_datetime(tasks_df["Timestamp"])
        req_df = pd.DataFrame(request_count)
        req_df["Timestamp"] = pd.to_datetime(req_df["Timestamp"])
        
        # Find scaling events
        events = detect_scaling_events(ml_tasks)
        if events:
            ax = axes[0, 1]
            event_times = [e[0] for e in events[:20]]  # Limit to 20 events
            event_deltas = [e[2] for e in events[:20]]
            
            colors = ["green" if e[1] == "scale_up" else "red" for e in events[:20]]
            ax.barh(range(len(event_times)), event_deltas, color=colors, alpha=0.7)
            ax.set_yticks(range(len(event_times)))
            ax.set_yticklabels([t.strftime("%H:%M:%S") for t in event_times], fontsize=8)
            ax.set_xlabel("Task Count Change", fontsize=11)
            ax.set_ylabel("Time", fontsize=11)
            ax.set_title("Scaling Events", fontsize=12, fontweight="bold")
            ax.grid(True, alpha=0.3, axis="x")
    
    # 3. Resource utilization per task
    backend_cpu = metrics.get("backend_cpu", [])
    if backend_cpu and backend_tasks:
        cpu_df = pd.DataFrame(backend_cpu)
        cpu_df["Timestamp"] = pd.to_datetime(cpu_df["Timestamp"])
        tasks_df = pd.DataFrame(backend_tasks)
        tasks_df["Timestamp"] = pd.to_datetime(tasks_df["Timestamp"])
        
        merged = pd.merge_asof(cpu_df.sort_values("Timestamp"), 
                               tasks_df.sort_values("Timestamp"),
                               on="Timestamp", suffixes=("_cpu", "_tasks"))
        
        if len(merged) > 0:
            cpu_per_task = merged["Average_cpu"] / merged["Average_tasks"].replace(0, np.nan)
            
            ax = axes[1, 0]
            ax.plot(merged["Timestamp"], cpu_per_task, "red", 
                   linewidth=2.5, marker="o", markersize=3, alpha=0.8)
            ax.fill_between(merged["Timestamp"], cpu_per_task, alpha=0.3, color="red")
            ax.set_xlabel("Time", fontsize=11)
            ax.set_ylabel("CPU per Task (%)", fontsize=11)
            ax.set_title("Resource Efficiency (CPU per Task)", fontsize=12, fontweight="bold")
            ax.grid(True, alpha=0.3)
    
    # 4. Scale-down efficiency
    if ml_tasks:
        tasks_df = pd.DataFrame(ml_tasks)
        tasks_df["Timestamp"] = pd.to_datetime(tasks_df["Timestamp"])
        
        # Calculate rate of change
        tasks_df_sorted = tasks_df.sort_values("Timestamp")
        time_diffs = tasks_df_sorted["Timestamp"].diff().dt.total_seconds()
        task_diffs = tasks_df_sorted["Average"].diff()
        change_rate = task_diffs / time_diffs
        
        ax = axes[1, 1]
        ax.plot(tasks_df_sorted["Timestamp"], change_rate, "purple", 
               linewidth=2.5, marker="s", markersize=3, alpha=0.8)
        ax.axhline(y=0, color="black", linestyle="-", linewidth=0.5, alpha=0.5)
        ax.fill_between(tasks_df_sorted["Timestamp"], change_rate, 0, 
                       where=(change_rate >= 0), alpha=0.3, color="green", label="Scale Up")
        ax.fill_between(tasks_df_sorted["Timestamp"], change_rate, 0, 
                       where=(change_rate < 0), alpha=0.3, color="red", label="Scale Down")
        ax.set_xlabel("Time", fontsize=11)
        ax.set_ylabel("Task Count Change Rate (tasks/sec)", fontsize=11)
        ax.set_title("Scaling Rate", fontsize=12, fontweight="bold")
        ax.legend()
        ax.grid(True, alpha=0.3)
    
    plt.xticks(rotation=45)
    plt.tight_layout()
    add_test_metadata(fig, test_name)
    
    output_path = Path(GRAPH_OUTPUT_DIR) / output_file
    output_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(output_path, dpi=300, bbox_inches="tight")
    plt.close()
    logger.info(f"Saved graph: {output_path}")


def plot_performance_degradation(
    metrics: Dict,
    locust_stats_history: pd.DataFrame = None,
    output_file: str = "performance_degradation.png",
    test_name: Optional[str] = None
):
    """Plot performance degradation indicators"""
    fig, axes = plt.subplots(2, 2, figsize=(16, 12))
    
    # 1. Latency trend
    if locust_stats_history is not None and not locust_stats_history.empty:
        if "Total Average Response Time" in locust_stats_history.columns:
            response_times = locust_stats_history["Total Average Response Time"].dropna()
            time_col = "datetime" if "datetime" in locust_stats_history.columns else "Timestamp"
            timestamps = locust_stats_history[time_col] if time_col in locust_stats_history.columns else range(len(response_times))
            
            if len(response_times) > 0:
                ax = axes[0, 0]
                ax.plot(timestamps, response_times, "blue", linewidth=2, alpha=0.7, label="Latency")
                
                # Add trend line
                if len(response_times) > 5:
                    z = np.polyfit(range(len(response_times)), response_times, 1)
                    p = np.poly1d(z)
                    trend = p(range(len(response_times)))
                    ax.plot(timestamps, trend, "red", linestyle="--", 
                           linewidth=2.5, label="Trend")
                    
                    # Calculate degradation
                    if z[0] > 0:
                        ax.text(0.05, 0.95, f"Degrading: +{z[0]:.2f}ms/sample", 
                               transform=ax.transAxes, fontsize=10, 
                               verticalalignment="top", color="red",
                               bbox=dict(boxstyle="round", facecolor="lightcoral", alpha=0.7))
                    else:
                        ax.text(0.05, 0.95, f"Improving: {z[0]:.2f}ms/sample", 
                               transform=ax.transAxes, fontsize=10, 
                               verticalalignment="top", color="green",
                               bbox=dict(boxstyle="round", facecolor="lightgreen", alpha=0.7))
                
                ax.set_xlabel("Time", fontsize=11)
                ax.set_ylabel("Response Time (ms)", fontsize=11)
                ax.set_title("Latency Trend Analysis", fontsize=12, fontweight="bold")
                ax.legend()
                ax.grid(True, alpha=0.3)
    
    # 2. Error rate trend
    error_5xx = metrics.get("alb_http_5xx", [])
    if error_5xx:
        error_df = pd.DataFrame(error_5xx)
        error_df["Timestamp"] = pd.to_datetime(error_df["Timestamp"])
        
        ax = axes[0, 1]
        ax.plot(error_df["Timestamp"], error_df["Average"], "red", 
               linewidth=2.5, marker="x", markersize=4, alpha=0.8, label="5xx Errors")
        
        # Add trend
        if len(error_df) > 5:
            z = np.polyfit(range(len(error_df)), error_df["Average"], 1)
            p = np.poly1d(z)
            ax.plot(error_df["Timestamp"], p(range(len(error_df))), 
                   "darkred", linestyle="--", linewidth=2.5, label="Trend")
        
        ax.set_xlabel("Time", fontsize=11)
        ax.set_ylabel("Error Count", fontsize=11)
        ax.set_title("Error Rate Trend", fontsize=12, fontweight="bold")
        ax.legend()
        ax.grid(True, alpha=0.3)
    
    # 3. Queue backlog trend
    queue_depth = metrics.get("sqs_queue_depth", [])
    if queue_depth:
        queue_df = pd.DataFrame(queue_depth)
        queue_df["Timestamp"] = pd.to_datetime(queue_df["Timestamp"])
        
        ax = axes[1, 0]
        ax.plot(queue_df["Timestamp"], queue_df["Average"], "orange", 
               linewidth=2.5, marker="o", markersize=3, alpha=0.8, label="Queue Depth")
        
        # Add trend
        if len(queue_df) > 5:
            z = np.polyfit(range(len(queue_df)), queue_df["Average"], 1)
            p = np.poly1d(z)
            trend = p(range(len(queue_df)))
            ax.plot(queue_df["Timestamp"], trend, "red", linestyle="--", 
                   linewidth=2.5, label="Trend")
            
            if z[0] > 0:
                ax.text(0.05, 0.95, f"Backlog Growing: +{z[0]:.2f}msg/sample", 
                       transform=ax.transAxes, fontsize=10, 
                       verticalalignment="top", color="red",
                       bbox=dict(boxstyle="round", facecolor="lightcoral", alpha=0.7))
        
        ax.set_xlabel("Time", fontsize=11)
        ax.set_ylabel("Queue Depth (messages)", fontsize=11)
        ax.set_title("Queue Backlog Trend", fontsize=12, fontweight="bold")
        ax.legend()
        ax.grid(True, alpha=0.3)
    
    # 4. Performance regression indicators
    if locust_stats_history is not None and not locust_stats_history.empty:
        if "Total Average Response Time" in locust_stats_history.columns:
            response_times = locust_stats_history["Total Average Response Time"].dropna()
            
            if len(response_times) > 10:
                # Divide into early and late periods
                early_period = response_times.iloc[:len(response_times)//2]
                late_period = response_times.iloc[len(response_times)//2:]
                
                ax = axes[1, 1]
                ax.boxplot([early_period.values, late_period.values], 
                          labels=["Early Period", "Late Period"], patch_artist=True)
                for patch in ax.artists:
                    patch.set_facecolor("lightblue")
                    patch.set_alpha(0.7)
                
                # Calculate regression
                early_mean = early_period.mean()
                late_mean = late_period.mean()
                regression_pct = ((late_mean - early_mean) / early_mean * 100) if early_mean > 0 else 0
                
                color = "red" if regression_pct > 10 else "orange" if regression_pct > 5 else "green"
                ax.text(0.5, 0.95, f"Regression: {regression_pct:+.1f}%", 
                       transform=ax.transAxes, fontsize=11, 
                       ha="center", verticalalignment="top", color=color,
                       bbox=dict(boxstyle="round", facecolor="wheat", alpha=0.7))
                
                ax.set_ylabel("Response Time (ms)", fontsize=11)
                ax.set_title("Performance Regression Analysis", fontsize=12, fontweight="bold")
                ax.grid(True, alpha=0.3, axis="y")
    
    plt.xticks(rotation=45)
    plt.tight_layout()
    add_test_metadata(fig, test_name)
    
    output_path = Path(GRAPH_OUTPUT_DIR) / output_file
    output_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(output_path, dpi=300, bbox_inches="tight")
    plt.close()
    logger.info(f"Saved graph: {output_path}")


# ============================================================================
# Main Generation Function
# ============================================================================

def generate_all_graphs(
    locust_csv: Optional[str] = None,
    cloudwatch_json: Optional[str] = None,
    test_name: Optional[str] = None
):
    """Generate essential metric graphs from test results"""
    logger.info("Generating essential metric graphs...")
    
    metrics = {}
    locust_df = pd.DataFrame()
    locust_stats_history = None
    
    if cloudwatch_json:
        metrics = load_cloudwatch_metrics(cloudwatch_json)
    
    if locust_csv:
        locust_df = load_locust_csv(locust_csv)
        locust_stats_history = load_locust_stats_history(locust_csv)
    
    # Align timestamps
    if not locust_df.empty and metrics:
        locust_df, metrics = align_timestamps(locust_df, metrics)
    
    # Generate only essential metric graphs (no test-specific metadata)
    # 1. Latency - Most critical for user experience
    plot_latency_over_time(locust_df, locust_stats_history, metrics, test_name=None)
    
    # 2. Throughput & Scaling - System capacity and scalability
    plot_throughput_vs_task_count(metrics, locust_df, test_name=None)
    plot_autoscaling_response(metrics, test_name=None)
    
    # 3. Error Rate - System reliability
    plot_error_rate_over_time(metrics, locust_stats_history, test_name=None)
    
    # 4. Queue Health - System backlog and processing
    plot_queue_depth_over_time(metrics, test_name=None)
    
    # 5. Resource Utilization - System efficiency
    plot_resource_utilization(metrics, test_name=None)
    
    logger.info("Essential metric graph generation complete")


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO)
    
    locust_csv = sys.argv[1] if len(sys.argv) > 1 else None
    cloudwatch_json = sys.argv[2] if len(sys.argv) > 2 else None
    
    generate_all_graphs(locust_csv, cloudwatch_json)

