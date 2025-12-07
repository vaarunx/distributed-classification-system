# Use Python base image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install CPU-only PyTorch first (much smaller than full PyTorch with CUDA)
# This saves ~1-2GB compared to the full PyTorch package
RUN pip install --no-cache-dir torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu

# Install other Python dependencies (excluding torch packages already installed)
# Create a filtered requirements file without torch packages
RUN grep -vE "^(torch|torchvision|torchaudio|#|$)" requirements.txt > requirements_no_torch.txt && \
    pip install --no-cache-dir -r requirements_no_torch.txt && \
    rm requirements_no_torch.txt

# Copy application code (models_cache excluded via .dockerignore)
COPY . .

# Create directories for model caching (models downloaded at runtime, not in image)
RUN mkdir -p /root/.cache/huggingface

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV TRANSFORMERS_CACHE=/root/.cache/huggingface
ENV HF_HOME=/root/.cache/huggingface

# Expose port
EXPOSE 8000

# Run the application with uvicorn
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]