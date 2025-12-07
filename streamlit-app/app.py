"""Streamlit app for Distributed Image Classification System"""
import os
import streamlit as st
import time
from datetime import datetime
from typing import List, Dict, Any, Optional
from PIL import Image
import io
import mimetypes
import pandas as pd

from utils.api_client import APIClient
from utils.s3_client import upload_to_s3

# Page configuration
st.set_page_config(
    page_title="Image Classification System",
    page_icon="🖼️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize API client (without caching to avoid recursion issues)
def get_api_client():
    backend_url = os.getenv("BACKEND_API_URL", "http://localhost:8080")
    return APIClient(backend_url)

api_client = get_api_client()

# Initialize session state
if "uploaded_images" not in st.session_state:
    st.session_state.uploaded_images = {}  # {s3_key: {filename, size, uploaded_at}}
if "active_jobs" not in st.session_state:
    st.session_state.active_jobs = {}  # {job_id: {job_data, status, created_at}}
if "job_results" not in st.session_state:
    st.session_state.job_results = {}  # {job_id: result_data}
if "selected_images" not in st.session_state:
    st.session_state.selected_images = []  # List of s3_keys
if "gallery_images" not in st.session_state:
    st.session_state.gallery_images = []
if "last_gallery_refresh" not in st.session_state:
    st.session_state.last_gallery_refresh = 0
if "job_history" not in st.session_state:
    st.session_state.job_history = []  # List of job summaries
if "last_history_refresh" not in st.session_state:
    st.session_state.last_history_refresh = 0
if "custom_categories" not in st.session_state:
    st.session_state.custom_categories = {}  # {category_name: [label1, label2, ...]}


def refresh_gallery():
    """Refresh the image gallery from backend"""
    try:
        images = api_client.list_images()
        st.session_state.gallery_images = images
        st.session_state.last_gallery_refresh = time.time()
        return True
    except Exception as e:
        st.error(f"Failed to refresh gallery: {str(e)}")
        return False


def get_image_content_type(filename: str) -> str:
    """Get content type from filename"""
    content_type, _ = mimetypes.guess_type(filename)
    return content_type or "image/jpeg"


# Sidebar configuration
with st.sidebar:
    st.title("⚙️ Configuration")
    
    backend_url = st.text_input(
        "Backend API URL",
        value=os.getenv("BACKEND_API_URL", "http://localhost:8080"),
        help="URL of the backend API service"
    )
    
    # Update API client URL if changed
    if backend_url != api_client.base_url:
        api_client.base_url = backend_url.rstrip("/")
        # Clear health check result when URL changes
        if "health_check_result" in st.session_state:
            del st.session_state.health_check_result
        # Don't rerun automatically - let user continue working
    
    st.divider()
    
    # Health check
    if st.button("🔍 Check Backend Health"):
        # Ensure API client uses current URL
        api_client.base_url = backend_url.rstrip("/")
        
        with st.spinner("Checking backend health..."):
            try:
                health = api_client.health_check()
                st.session_state.health_check_result = {
                    "status": "success",
                    "data": health,
                    "url": api_client.base_url
                }
                st.success(f"✅ Backend is {health.get('status', 'unknown')}")
                if health.get("service"):
                    st.info(f"Service: {health.get('service')}")
                if health.get("time"):
                    st.caption(f"Checked at: {health.get('time')}")
            except Exception as e:
                st.session_state.health_check_result = {
                    "status": "error",
                    "error": str(e),
                    "url": api_client.base_url
                }
                st.error(f"❌ Backend health check failed: {str(e)}")
                st.caption(f"URL: {api_client.base_url}")
    
    # Show last health check result if available
    if "health_check_result" in st.session_state:
        result = st.session_state.health_check_result
        if result.get("status") == "success":
            st.caption(f"Last check: ✅ {result.get('url', 'N/A')}")
        elif result.get("status") == "error":
            st.caption(f"Last check: ❌ {result.get('url', 'N/A')}")
    
    # Refresh API client (recreate with current settings)
    if st.button("🔄 Refresh API Client"):
        api_client.base_url = backend_url.rstrip("/")
        st.success("API client refreshed!")
        st.rerun()
    
    st.divider()
    
    # Gallery refresh
    if st.button("🔄 Refresh Gallery"):
        with st.spinner("Refreshing gallery..."):
            refresh_gallery()
            st.success("Gallery refreshed!")
    
    st.divider()
    
    # Custom Categories Management
    st.subheader("📁 Custom Categories")
    with st.expander("Manage Categories", expanded=False):
        # Create new category
        st.markdown("**Create New Category**")
        new_category_name = st.text_input(
            "Category Name",
            key="new_category_name",
            placeholder="e.g., Animals, Vehicles",
            help="Enter a name for your category"
        )
        new_category_labels = st.text_area(
            "Labels (one per line or comma-separated)",
            key="new_category_labels",
            placeholder="dog\ncat\nbird\nor\ndog, cat, bird",
            help="Enter the labels for this category"
        )
        
        if st.button("💾 Save Category", key="save_category"):
            if new_category_name and new_category_labels:
                # Parse labels
                if "\n" in new_category_labels:
                    labels = [label.strip() for label in new_category_labels.split("\n") if label.strip()]
                else:
                    labels = [label.strip() for label in new_category_labels.split(",") if label.strip()]
                
                if labels:
                    st.session_state.custom_categories[new_category_name] = labels
                    st.success(f"Category '{new_category_name}' saved with {len(labels)} labels!")
                    st.rerun()
                else:
                    st.error("Please provide at least one label")
            else:
                st.error("Please provide both category name and labels")
        
        st.divider()
        
        # List and manage existing categories
        if st.session_state.custom_categories:
            st.markdown("**Existing Categories**")
            for cat_name, labels in list(st.session_state.custom_categories.items()):
                with st.container():
                    col1, col2 = st.columns([3, 1])
                    with col1:
                        st.markdown(f"**{cat_name}** ({len(labels)} labels)")
                        st.caption(f"Labels: {', '.join(labels[:5])}{'...' if len(labels) > 5 else ''}")
                    with col2:
                        if st.button("🗑️", key=f"delete_cat_{cat_name}", help="Delete category"):
                            del st.session_state.custom_categories[cat_name]
                            st.rerun()
                    st.divider()
        else:
            st.info("No categories saved yet. Create one above!")


# Main title
st.title("🖼️ Image Classification System")
st.markdown("Upload images, submit classification jobs, and view results")

# Tabs for different sections
tab1, tab2, tab3, tab4, tab5 = st.tabs(["📤 Upload Images", "🖼️ Image Gallery", "📋 Submit Job", "📊 Job Status & Results", "📜 Job History"])


# Tab 1: Upload Images
with tab1:
    st.header("Upload Images")
    st.markdown("Upload one or more images to S3 for classification")
    
    uploaded_files = st.file_uploader(
        "Choose image files",
        type=["jpg", "jpeg", "png", "gif", "bmp", "webp"],
        accept_multiple_files=True,
        help="Select one or more image files to upload"
    )
    
    if uploaded_files:
        if st.button("📤 Upload All Images", type="primary"):
            progress_bar = st.progress(0)
            status_text = st.empty()
            success_count = 0
            error_count = 0
            
            for idx, uploaded_file in enumerate(uploaded_files):
                try:
                    # Read file data
                    file_data = uploaded_file.read()
                    filename = uploaded_file.name
                    content_type = get_image_content_type(filename)
                    
                    # Get presigned URL
                    status_text.text(f"Getting upload URL for {filename}...")
                    upload_info = api_client.get_upload_url(filename, content_type)
                    
                    # Upload to S3
                    status_text.text(f"Uploading {filename} to S3...")
                    success = upload_to_s3(
                        upload_info["upload_url"],
                        file_data,
                        content_type
                    )
                    
                    if success:
                        s3_key = upload_info["s3_key"]
                        st.session_state.uploaded_images[s3_key] = {
                            "filename": filename,
                            "size": len(file_data),
                            "uploaded_at": datetime.now().isoformat(),
                            "s3_key": s3_key
                        }
                        success_count += 1
                    else:
                        error_count += 1
                        st.error(f"Failed to upload {filename}")
                    
                    # Update progress
                    progress_bar.progress((idx + 1) / len(uploaded_files))
                    
                except Exception as e:
                    error_count += 1
                    st.error(f"Error uploading {uploaded_file.name}: {str(e)}")
                    progress_bar.progress((idx + 1) / len(uploaded_files))
            
            status_text.empty()
            if success_count > 0:
                st.success(f"✅ Successfully uploaded {success_count} image(s)")
                if error_count > 0:
                    st.warning(f"⚠️ {error_count} image(s) failed to upload")
                # Refresh gallery
                refresh_gallery()
            else:
                st.error("❌ All uploads failed")
    
    # Show recently uploaded images
    if st.session_state.uploaded_images:
        st.subheader("Recently Uploaded Images")
        for s3_key, info in list(st.session_state.uploaded_images.items())[-10:]:
            col1, col2 = st.columns([3, 1])
            with col1:
                st.text(f"📄 {info['filename']} ({s3_key})")
            with col2:
                if st.button("🗑️", key=f"delete_uploaded_{s3_key}", help="Remove from list"):
                    del st.session_state.uploaded_images[s3_key]
                    st.rerun()


# Tab 2: Image Gallery
with tab2:
    st.header("Image Gallery")
    st.markdown("Browse and manage images in S3")
    
    col1, col2 = st.columns([3, 1])
    with col1:
        st.markdown("**Available Images**")
    with col2:
        if st.button("🔄 Refresh", key="refresh_gallery_tab"):
            refresh_gallery()
    
    # Auto-refresh gallery if it's been more than 30 seconds
    if time.time() - st.session_state.last_gallery_refresh > 30:
        refresh_gallery()
    
    if not st.session_state.gallery_images:
        st.info("No images found. Upload some images first!")
    else:
        # Filter and search
        search_term = st.text_input("🔍 Search images", placeholder="Filter by filename...")
        
        filtered_images = st.session_state.gallery_images
        if search_term:
            filtered_images = [
                img for img in filtered_images
                if search_term.lower() in img["key"].lower()
            ]
        
        st.markdown(f"**Found {len(filtered_images)} image(s)**")
        
        # Display images in grid
        num_cols = 4
        for i in range(0, len(filtered_images), num_cols):
            cols = st.columns(num_cols)
            for j, img_info in enumerate(filtered_images[i:i+num_cols]):
                with cols[j]:
                    s3_key = img_info["key"]
                    filename = s3_key.split("/")[-1]
                    
                    # Checkbox for selection
                    is_selected = s3_key in st.session_state.selected_images
                    selected = st.checkbox(
                        filename[:30] + ("..." if len(filename) > 30 else ""),
                        value=is_selected,
                        key=f"select_{s3_key}"
                    )
                    
                    if selected and not is_selected:
                        st.session_state.selected_images.append(s3_key)
                    elif not selected and is_selected:
                        st.session_state.selected_images.remove(s3_key)
                    
                    # Image metadata
                    size_mb = img_info["size"] / (1024 * 1024)
                    st.caption(f"{size_mb:.2f} MB")
                    st.caption(f"📅 {img_info['last_modified'][:10]}")
                    
                    # Delete button
                    if st.button("🗑️ Delete", key=f"delete_{s3_key}"):
                        try:
                            result = api_client.delete_image(s3_key)
                            if result.get("success"):
                                st.success(f"Deleted {filename}")
                                refresh_gallery()
                                if s3_key in st.session_state.selected_images:
                                    st.session_state.selected_images.remove(s3_key)
                                time.sleep(0.5)
                                st.rerun()
                            else:
                                st.error(f"Failed to delete: {result.get('message', 'Unknown error')}")
                        except Exception as e:
                            st.error(f"Error deleting image: {str(e)}")
        
        # Bulk actions
        if st.session_state.selected_images:
            st.divider()
            st.markdown(f"**{len(st.session_state.selected_images)} image(s) selected**")
            col1, col2 = st.columns(2)
            with col1:
                if st.button("❌ Clear Selection"):
                    st.session_state.selected_images = []
                    st.rerun()
            with col2:
                if st.button("🗑️ Delete Selected", type="primary"):
                    deleted = 0
                    for s3_key in st.session_state.selected_images[:]:
                        try:
                            result = api_client.delete_image(s3_key)
                            if result.get("success"):
                                deleted += 1
                                st.session_state.selected_images.remove(s3_key)
                        except:
                            pass
                    if deleted > 0:
                        st.success(f"Deleted {deleted} image(s)")
                        refresh_gallery()
                        time.sleep(0.5)
                        st.rerun()


# Tab 3: Submit Job
with tab3:
    st.header("Submit Classification Job")
    st.markdown("Configure and submit a classification job")
    
    # Job type selection
    job_type = st.radio(
        "Job Type",
        ["image_classification", "custom_classification"],
        format_func=lambda x: "Image Classification (MobileNet)" if x == "image_classification" else "Custom Classification (CLIP)",
        help="Standard classification uses ImageNet labels, Custom uses your own labels"
    )
    
    # Get available images
    available_images = []
    if st.session_state.gallery_images:
        available_images = [img["key"] for img in st.session_state.gallery_images]
    
    if not available_images:
        st.warning("⚠️ No images available. Please upload images first!")
    else:
        # Image selection
        st.subheader("Select Images")
        selected_s3_keys = st.multiselect(
            "Choose images to classify",
            options=available_images,
            default=st.session_state.selected_images if st.session_state.selected_images else [],
            format_func=lambda x: x.split("/")[-1],
            help="Select one or more images for classification"
        )
        
        if not selected_s3_keys:
            st.info("Please select at least one image")
        else:
            st.success(f"✅ {len(selected_s3_keys)} image(s) selected")
            
            # Custom labels (only for custom classification)
            custom_labels = []
            if job_type == "custom_classification":
                st.subheader("Custom Labels")
                
                # Choose between saved category or manual entry
                if st.session_state.custom_categories:
                    label_source = st.radio(
                        "Label Source",
                        ["Use saved category", "Enter custom labels"],
                        key="label_source",
                        help="Choose to use a saved category or enter labels manually"
                    )
                else:
                    label_source = "Enter custom labels"
                
                if label_source == "Use saved category":
                    # Select from saved categories
                    category_names = list(st.session_state.custom_categories.keys())
                    selected_category = st.selectbox(
                        "Select Category",
                        options=category_names,
                        key="selected_category",
                        help="Choose a saved category to use"
                    )
                    
                    if selected_category:
                        custom_labels = st.session_state.custom_categories[selected_category]
                        st.success(f"✅ Using category '{selected_category}' with {len(custom_labels)} labels")
                        with st.expander("View Labels", expanded=False):
                            st.write(", ".join(custom_labels))
                else:
                    # Manual entry with improved UI
                    labels_input = st.text_area(
                        "Enter custom labels (one per line or comma-separated)",
                        placeholder="dog\ncat\nbird\nor\ndog, cat, bird",
                        help="Enter the labels you want to classify against",
                        key="manual_labels_input"
                    )
                    
                    if labels_input:
                        # Parse labels (support both newline and comma separation)
                        if "\n" in labels_input:
                            custom_labels = [label.strip() for label in labels_input.split("\n") if label.strip()]
                        else:
                            custom_labels = [label.strip() for label in labels_input.split(",") if label.strip()]
                        
                        # Show preview
                        if custom_labels:
                            st.info(f"📋 {len(custom_labels)} label(s) parsed: {', '.join(custom_labels[:10])}{'...' if len(custom_labels) > 10 else ''}")
                
                if not custom_labels:
                    st.warning("⚠️ Please provide custom labels for custom classification")
            
            # Configuration
            st.subheader("Configuration")
            col1, col2 = st.columns(2)
            
            with col1:
                top_k = st.slider(
                    "Top K",
                    min_value=1,
                    max_value=10,
                    value=5,
                    help="Number of top predictions to return per image"
                )
            
            with col2:
                confidence_threshold = st.slider(
                    "Confidence Threshold",
                    min_value=0.0,
                    max_value=1.0,
                    value=0.5,
                    step=0.05,
                    help="Minimum confidence score. Below this, images are marked as 'unknown'"
                )
            
            # Submit button
            st.divider()
            if st.button("🚀 Submit Job", type="primary", disabled=not selected_s3_keys or (job_type == "custom_classification" and not custom_labels)):
                try:
                    job_data = {
                        "job_type": job_type,
                        "s3_keys": selected_s3_keys,
                        "top_k": top_k,
                        "confidence_threshold": confidence_threshold
                    }
                    
                    if custom_labels:
                        job_data["custom_labels"] = custom_labels
                    
                    with st.spinner("Submitting job..."):
                        response = api_client.submit_job(job_data)
                    
                    job_id = response.get("job_id")
                    if job_id:
                        st.success(f"✅ Job submitted successfully! Job ID: {job_id}")
                        
                        # Add to active jobs
                        st.session_state.active_jobs[job_id] = {
                            "job_data": job_data,
                            "status": response.get("status", "queued"),
                            "created_at": datetime.now().isoformat(),
                            "job_id": job_id
                        }
                        
                        # Clear selection
                        st.session_state.selected_images = []
                        
                        # Switch to results tab
                        st.info("📊 Check the 'Job Status & Results' tab to monitor progress")
                    else:
                        st.error("Failed to submit job: No job ID returned")
                        
                except Exception as e:
                    st.error(f"❌ Error submitting job: {str(e)}")


# Tab 4: Job Status & Results
with tab4:
    st.header("Job Status & Results")
    st.markdown("Monitor active jobs and view results")
    
    # Auto-refresh toggle
    auto_refresh = st.checkbox("🔄 Auto-refresh (every 5 seconds)", value=False)
    
    # Refresh button
    if st.button("🔄 Manual Refresh"):
        st.rerun()
    
    # Auto-refresh using a different approach to avoid infinite loops
    # Only rerun if auto-refresh is enabled AND we haven't just refreshed
    if auto_refresh:
        # Check if we should auto-refresh (avoid immediate rerun)
        if "last_auto_refresh" not in st.session_state:
            st.session_state.last_auto_refresh = time.time()
        
        elapsed = time.time() - st.session_state.last_auto_refresh
        if elapsed >= 5:
            st.session_state.last_auto_refresh = time.time()
            st.rerun()
        else:
            remaining = int(5 - elapsed)
            st.caption(f"⏳ Auto-refreshing in {remaining} seconds...")
    
    if not st.session_state.active_jobs:
        st.info("No active jobs. Submit a job from the 'Submit Job' tab!")
    else:
        # Display active jobs
        for job_id, job_info in list(st.session_state.active_jobs.items()):
            with st.expander(f"Job: {job_id} - Status: {job_info['status'].upper()}", expanded=True):
                # Get latest status
                try:
                    status_data = api_client.get_job_status(job_id)
                    job_info["status"] = status_data.get("status", job_info["status"])
                    
                    # Update in session state
                    st.session_state.active_jobs[job_id]["status"] = job_info["status"]
                    
                    # Display job info
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.markdown(f"**Job ID:**\n`{job_id}`")
                        st.markdown(f"**Type:** {job_info['job_data'].get('job_type', 'N/A')}")
                    with col2:
                        st.markdown(f"**Status:** {job_info['status']}")
                        st.markdown(f"**Created:** {job_info['created_at'][:19]}")
                    with col3:
                        num_images = len(job_info['job_data'].get('s3_keys', []))
                        st.markdown(f"**Images:** {num_images}")
                        st.markdown(f"**Top K:** {job_info['job_data'].get('top_k', 5)}")
                    
                    # Status badge
                    status = job_info["status"]
                    if status == "completed":
                        st.success("✅ Job completed!")
                    elif status == "failed":
                        st.error(f"❌ Job failed: {status_data.get('error', 'Unknown error')}")
                    elif status in ["pending", "queued", "processing", "retrying"]:
                        st.info(f"⏳ Job is {status}...")
                    
                    # Show results if completed
                    if status == "completed":
                        try:
                            if job_id not in st.session_state.job_results:
                                result_data = api_client.get_job_result(job_id)
                                st.session_state.job_results[job_id] = result_data
                            else:
                                result_data = st.session_state.job_results[job_id]
                            
                            # Display results
                            st.divider()
                            st.subheader("📊 Results")
                            
                            # Summary
                            summary = result_data.get("summary", {})
                            col1, col2, col3, col4 = st.columns(4)
                            with col1:
                                st.metric("Total Images", summary.get("total", 0))
                            with col2:
                                st.metric("Classified", summary.get("classified", 0))
                            with col3:
                                st.metric("Unknown", summary.get("unknown", 0))
                            with col4:
                                processing_time = result_data.get("processing_time_ms", 0)
                                st.metric("Processing Time", f"{processing_time:.0f} ms")
                            
                            # Model used
                            model_used = result_data.get("model_used", "N/A")
                            st.markdown(f"**Model:** {model_used}")
                            
                            # Grouped by label
                            grouped = result_data.get("grouped_by_label", {})
                            if grouped:
                                st.subheader("📁 Images Grouped by Label")
                                for label, filenames in grouped.items():
                                    # Use a container instead of expander to avoid nesting inside job expander
                                    with st.container():
                                        st.markdown(f"**🏷️ {label}** ({len(filenames)} image{'s' if len(filenames) != 1 else ''})")
                                        # Display filenames in a compact format
                                        if len(filenames) <= 10:
                                            # Show all if 10 or fewer
                                            for filename in filenames:
                                                st.text(f"  • {filename}")
                                        else:
                                            # Show first 10 with count of remaining
                                            for filename in filenames[:10]:
                                                st.text(f"  • {filename}")
                                            st.caption(f"... and {len(filenames) - 10} more image{'s' if len(filenames) - 10 != 1 else ''}")
                                        st.divider()
                            
                            # Detailed results table
                            detailed = result_data.get("detailed_results", [])
                            if detailed:
                                st.subheader("📋 Detailed Results")
                                
                                # Create table data
                                table_data = []
                                for result in detailed:
                                    table_data.append({
                                        "Filename": result.get("filename", "N/A"),
                                        "Top Prediction": result.get("top_prediction", "N/A"),
                                        "Confidence": f"{result.get('top_confidence', 0):.2%}",
                                        "Processing Time": f"{result.get('processing_time_ms', 0):.0f} ms"
                                    })
                                
                                st.dataframe(table_data, use_container_width=True)
                            
                        except Exception as e:
                            st.error(f"Error fetching results: {str(e)}")
                    
                    # Remove button for completed/failed jobs
                    if status in ["completed", "failed"]:
                        if st.button("🗑️ Remove from list", key=f"remove_{job_id}"):
                            del st.session_state.active_jobs[job_id]
                            if job_id in st.session_state.job_results:
                                del st.session_state.job_results[job_id]
                            st.rerun()
                    
                except Exception as e:
                    st.error(f"Error fetching job status: {str(e)}")
                    st.json(job_info)


# Tab 5: Job History
with tab5:
    st.header("Job History")
    st.markdown("View all submitted jobs with filtering and sorting")
    
    # Refresh function
    def refresh_job_history():
        """Refresh the job history from backend"""
        try:
            jobs = api_client.list_jobs(limit=100)
            st.session_state.job_history = jobs
            st.session_state.last_history_refresh = time.time()
            return True
        except Exception as e:
            st.error(f"Failed to refresh job history: {str(e)}")
            return False
    
    # Filters
    col1, col2, col3 = st.columns([2, 2, 1])
    with col1:
        status_filter = st.selectbox(
            "Filter by Status",
            options=["All", "pending", "queued", "processing", "retrying", "completed", "failed"],
            index=0,
            key="history_status_filter"
        )
    with col2:
        job_type_filter = st.selectbox(
            "Filter by Job Type",
            options=["All", "image_classification", "custom_classification"],
            index=0,
            key="history_type_filter"
        )
    with col3:
        if st.button("🔄 Refresh", key="refresh_history"):
            with st.spinner("Refreshing job history..."):
                refresh_job_history()
                st.success("Job history refreshed!")
    
    # Auto-refresh if it's been more than 30 seconds
    if time.time() - st.session_state.last_history_refresh > 30:
        refresh_job_history()
    
    # Load job history if empty
    if not st.session_state.job_history:
        refresh_job_history()
    
    # Apply filters
    filtered_jobs = st.session_state.job_history
    if status_filter != "All":
        filtered_jobs = [job for job in filtered_jobs if job.get("status") == status_filter]
    if job_type_filter != "All":
        filtered_jobs = [job for job in filtered_jobs if job.get("job_type") == job_type_filter]
    
    # Display results
    if not filtered_jobs:
        st.info("No jobs found matching the selected filters.")
    else:
        st.markdown(f"**Found {len(filtered_jobs)} job(s)**")
        
        # Create dataframe for display
        df_data = []
        for job in filtered_jobs:
            created_at = job.get("created_at", "")
            completed_at = job.get("completed_at")
            if isinstance(created_at, str):
                try:
                    created_at = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
                except:
                    pass
            if completed_at and isinstance(completed_at, str):
                try:
                    completed_at = datetime.fromisoformat(completed_at.replace("Z", "+00:00"))
                except:
                    completed_at = None
            
            df_data.append({
                "Job ID": job.get("job_id", "N/A")[:20] + "..." if len(job.get("job_id", "")) > 20 else job.get("job_id", "N/A"),
                "Status": job.get("status", "N/A").upper(),
                "Type": "MobileNet" if job.get("job_type") == "image_classification" else "CLIP",
                "Created": created_at.strftime("%Y-%m-%d %H:%M:%S") if isinstance(created_at, datetime) else str(created_at)[:19],
                "Completed": completed_at.strftime("%Y-%m-%d %H:%M:%S") if completed_at and isinstance(completed_at, datetime) else ("N/A" if not completed_at else str(completed_at)[:19]),
                "# Images": job.get("num_images", 0),
            })
        
        df = pd.DataFrame(df_data)
        
        # Display dataframe with row selection (requires Streamlit >= 1.28.0)
        selected_indices = st.dataframe(
            df,
            use_container_width=True,
            hide_index=True,
            on_select="rerun",
            selection_mode="single-row"
        )
        
        # Show details for selected job
        if hasattr(selected_indices, 'selection') and selected_indices.selection.rows:
            selected_idx = selected_indices.selection.rows[0]
            selected_job = filtered_jobs[selected_idx]
            job_id = selected_job.get("job_id")
            
            st.divider()
            st.subheader(f"Job Details: {job_id}")
            
            # Get full job details
            try:
                status_data = api_client.get_job_status(job_id)
                
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.markdown(f"**Job ID:**\n`{job_id}`")
                    st.markdown(f"**Type:** {selected_job.get('job_type', 'N/A')}")
                with col2:
                    st.markdown(f"**Status:** {status_data.get('status', 'N/A')}")
                    created_at = status_data.get("created_at", "")
                    if isinstance(created_at, str):
                        try:
                            created_at = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
                            st.markdown(f"**Created:** {created_at.strftime('%Y-%m-%d %H:%M:%S')}")
                        except:
                            st.markdown(f"**Created:** {created_at}")
                    else:
                        st.markdown(f"**Created:** {created_at}")
                with col3:
                    st.markdown(f"**Images:** {selected_job.get('num_images', 0)}")
                    if status_data.get("completed_at"):
                        completed_at = status_data.get("completed_at")
                        if isinstance(completed_at, str):
                            try:
                                completed_at = datetime.fromisoformat(completed_at.replace("Z", "+00:00"))
                                st.markdown(f"**Completed:** {completed_at.strftime('%Y-%m-%d %H:%M:%S')}")
                            except:
                                st.markdown(f"**Completed:** {completed_at}")
                        else:
                            st.markdown(f"**Completed:** {completed_at}")
                    
                # Show results if completed
                if status_data.get("status") == "completed":
                    try:
                        result_data = api_client.get_job_result(job_id)
                        
                        st.divider()
                        st.subheader("Results Summary")
                        
                        summary = result_data.get("summary", {})
                        col1, col2, col3, col4 = st.columns(4)
                        with col1:
                            st.metric("Total Images", summary.get("total", 0))
                        with col2:
                            st.metric("Classified", summary.get("classified", 0))
                        with col3:
                            st.metric("Unknown", summary.get("unknown", 0))
                        with col4:
                            processing_time = result_data.get("processing_time_ms", 0)
                            st.metric("Processing Time", f"{processing_time:.0f} ms")
                        
                        model_used = result_data.get("model_used", "N/A")
                        st.markdown(f"**Model:** {model_used}")
                        
                        # Quick link to view full results
                        st.info("💡 Switch to 'Job Status & Results' tab to view detailed results")
                        
                    except Exception as e:
                        st.error(f"Error fetching results: {str(e)}")
                elif status_data.get("status") == "failed":
                    error_msg = status_data.get("error", "Unknown error")
                    st.error(f"❌ Job failed: {error_msg}")
                
            except Exception as e:
                st.error(f"Error fetching job details: {str(e)}")

