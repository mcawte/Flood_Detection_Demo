FROM osgeo/gdal:ubuntu-small-3.6.3

# Install Python and essential build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3-pip python3-dev git build-essential \
    && rm -rf /var/lib/apt/lists/*

# Set environment variables
ENV PYTHONPATH="/app"

# Install Python dependencies in smaller groups with cache cleaning
# Core dependencies first
RUN pip3 install --no-cache-dir --upgrade pip setuptools wheel && \
    pip3 install --no-cache-dir boto3 requests mcp "gradio[mcp]" numpy sentinelhub rasterio && \
    pip3 install --no-cache-dir python-multipart pytorch-lightning==2.1.1

# ML dependencies
RUN pip3 install --no-cache-dir torch==2.1.0 torchvision==0.16.0 --index-url https://download.pytorch.org/whl/cpu

# Geo dependencies
RUN pip3 install --no-cache-dir rioxarray && \
    pip3 install --no-cache-dir global_land_mask

# Install terratorch
RUN pip3 install --no-cache-dir "terratorch @ git+https://github.com/IBM/terratorch.git@6d97521" && \
    pip3 install --no-cache-dir lightning-utilities

# Create directory structure
WORKDIR /app
RUN mkdir -p /app/data/input /app/data/output /app/configs /app/models && chmod -R 777 /app/models /app/configs /app/data

# Copy only necessary files
COPY ./app /app

# Expose MCP over HTTP
EXPOSE 8080

# Start MCP server with uvicorn
CMD ["python3", "main.py"]
