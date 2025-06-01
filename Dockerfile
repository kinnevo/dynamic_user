# Use Python 3.12 slim image for smaller size
FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Install system dependencies
RUN apt-get update && apt-get install -y \
    && rm -rf /var/lib/apt/lists/*

# Install pip uv for fast installs
RUN pip install uv

# Copy requirements first for better Docker layer caching
COPY requirements.txt .

# Install Python dependencies with uv
RUN uv pip install --no-cache-dir -r requirements.txt --system

# Copy the entire application
COPY . .

# Create non-root user for security
RUN useradd --create-home --shell /bin/bash app && chown -R app:app /app
USER app

# Expose the port that NiceGUI will run on
EXPOSE 8080

# Command to run the application
CMD ["python", "main.py"] 