FROM osgeo/gdal:ubuntu-small-3.6.3

# Install Python and essential build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3-pip python3-dev git build-essential \
    && rm -rf /var/lib/apt/lists/*

# Set environment variables
ENV PYTHONPATH="/app"

# Copy dependency manifests separately to leverage Docker layer caching
COPY requirements-backend.txt constraints-backend.txt /tmp/pip/

# Install Python dependencies with pinned versions
RUN pip3 install --no-cache-dir --upgrade pip setuptools wheel && \
    pip3 install --no-cache-dir --index-url https://download.pytorch.org/whl/cpu torch==2.1.0 torchvision==0.16.0 && \
    pip3 install --no-cache-dir --upgrade-strategy only-if-needed -r /tmp/pip/requirements-backend.txt -c /tmp/pip/constraints-backend.txt

# Create directory structure
WORKDIR /app
RUN mkdir -p /app/data/input /app/data/output /app/configs /app/models && chmod -R 777 /app/models /app/configs /app/data

# Copy only necessary files
COPY ./app /app

# Expose MCP over HTTP
EXPOSE 8080

# Start MCP server with uvicorn
CMD ["python3", "main.py"]
