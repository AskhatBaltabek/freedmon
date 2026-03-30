# Use Python 3.9 slim as base
FROM python:3.9-slim

# Install system dependencies
# tesseract-ocr: For OCR
# libgl1, libglib2.0-0: For OpenCV (headless)
RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    tesseract-ocr-eng \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Ensure snapshots directory exists
RUN mkdir -p snapshots

# Run the monitoring app
CMD ["python", "-u", "main.py"]
