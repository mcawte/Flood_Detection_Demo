# Flood Detection Demo - Monorepo

A complete flood detection system deployed on Kubernetes, featuring AI-powered geospatial inference, Streamlit frontend, and n8n workflow orchestration.

## Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Streamlit     │    │      n8n        │    │ Flood Inference │
│   Frontend      │◄──►│   Workflows     │◄──►│    Backend      │
│                 │    │                 │    │   (MCP Server)  │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         │                       │                       │
         ▼                       ▼                       ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│  Load Balancer  │    │  Configuration  │    │  MinIO Storage  │
│   (Ingress)     │    │   & Secrets     │    │   (Results)     │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

## Components

### 🌊 Flood Detection Backend (`flood-detection-backend/`)
- **Technology**: Python, PyTorch, terratorch, Gradio MCP
- **Purpose**: AI-powered flood detection using Prithvi geospatial model
- **Inputs**: Satellite imagery from Sentinel Hub
- **Outputs**: GeoTIFF prediction files uploaded to MinIO storage
- **API**: MCP (Model Context Protocol) server

### 🖥️ Streamlit Frontend (`flood-detection-frontend/`)
- **Technology**: Streamlit, Folium, OpenRouteService
- **Purpose**: User interface for flood detection requests and logistics management
- **Features**:
  - Coordinate-based flood detection requests
  - Route planning with hazard avoidance
  - Fleet management dashboard
  - Disaster management interface

### 🔄 n8n Workflows (`n8n-workflows/`)
- **Technology**: n8n workflow automation
- **Purpose**: Orchestrates communication between frontend and backend
- **Workflows**:
  - Flood detection request handling
  - Result processing and notification
  - Data pipeline management

### ⚙️ Helm Charts (`charts/`)
- **Purpose**: Kubernetes deployment configuration
- **Charts**:
  - `flood-detection-backend/`: Backend deployment
  - `flood-detection-frontend/`: Frontend deployment
  - `n8n/`: Workflow engine deployment
  - `minio/`: Object storage deployment

## Quick Start

### 🚀 Option 1: Docker Compose (5 minutes)
```bash
# Clone repository
git clone <repository-url>
cd flood-detection-demo

# Setup environment
cp .env.example .env
# Edit .env with your Sentinel Hub and OpenRouteService credentials
# Upload the model checkpoint to MinIO (see "Model assets" below)

# Start system
./scripts/start-local.sh

# Access at:
# Frontend: http://localhost:8501
# Backend: http://localhost:8080
# n8n: http://localhost:5678 (admin/admin123)
# MinIO: http://localhost:9000 (minioadmin/minioadmin123)
# n8n automatically imports workflows found in ./n8n-workflows on startup
```

### ☸️ Option 2: OpenShift Local (30 minutes)
```bash
# Install CRC (OpenShift Local)
# Download pull secret from Red Hat Developer Portal

crc setup
crc start --pull-secret-file ~/Downloads/pull-secret.txt

# Deploy system
export SH_CLIENT_ID="your_client_id"
export SH_CLIENT_SECRET="your_client_secret"
./openshift/scripts/deploy-openshift.sh
```

### 🏗️ Option 3: Production Kubernetes
```bash
# Deploy with Helm
helm install flood-detection ./charts/flood-detection-system \
  --set secrets.sentinelHub.clientId="$SH_CLIENT_ID" \
  --set secrets.sentinelHub.clientSecret="$SH_CLIENT_SECRET"
```

**📖 See [QUICKSTART.md](QUICKSTART.md) for detailed setup instructions**

## Model assets

The flood model relies on two artifacts:

- `config_granite_geospatial_uki_flood_detection_v1.yaml` – committed at
  `flood-detection-backend/configs/` and copied into the backend image during
  `docker build`. Edit this file in-repo when you need to change Terratorch
  behaviour.
- `granite_geospatial_uki_flood_detection_v1.ckpt` – kept out of git. On
  startup the backend downloads it from MinIO, so seed the bucket once per
  environment.

To upload the checkpoint into the local Docker Compose MinIO service:

```bash
# Create the bucket (safe to re-run)
docker run --rm --network flood-network -e MC_HOST_local=http://minioadmin:minioadmin123@minio:9000 minio/mc mb --ignore-existing local/flood-models

# Copy the checkpoint from ./model into MinIO
docker run --rm --network flood-network -e MC_HOST_local=http://minioadmin:minioadmin123@minio:9000 -v "$(pwd)/model:/data" minio/mc cp /data/granite_geospatial_uki_flood_detection_v1.ckpt local/flood-models/

# (Optional) confirm the upload
docker run --rm --network flood-network -e MC_HOST_local=http://minioadmin:minioadmin123@minio:9000 minio/mc ls local/flood-models
```

When deploying elsewhere, upload the same checkpoint (with the same filename)
to that environment’s MinIO/S3 bucket before starting the backend pods.

## Project Structure

```
flood-detection-demo/
├── README.md
├── docker-compose.yml
├── flood-detection-backend/     # AI inference service
│   ├── app/
│   │   ├── mcp_server.py       # MCP server implementation
│   │   ├── inference.py        # Flood detection logic
│   │   └── ...
│   ├── Dockerfile
│   ├── requirements.txt
│   └── configs/
├── flood-detection-frontend/    # Streamlit web app
│   ├── app.py                  # Main Streamlit app
│   ├── tabs/                   # Tab modules
│   ├── Dockerfile
│   └── requirements.txt
├── n8n-workflows/              # Workflow definitions
│   ├── flood-detection.json    # Main workflow
│   └── ...
├── charts/                     # Helm charts
│   ├── flood-detection-system/ # Umbrella chart
│   ├── flood-detection-backend/
│   ├── flood-detection-frontend/
│   ├── n8n/
│   └── minio/
└── docs/                       # Documentation
    ├── deployment.md
    ├── development.md
    └── api.md
```

## Technology Stack

- **AI/ML**: PyTorch, terratorch, Prithvi geospatial model
- **Backend**: Python, Gradio MCP, rasterio, sentinelhub
- **Frontend**: Streamlit, Folium maps, OpenRouteService
- **Workflow**: n8n automation platform
- **Storage**: MinIO object storage
- **Deployment**: Kubernetes, Helm, Docker
- **Monitoring**: Kubernetes native monitoring

## Key Features

1. **Automated Flood Detection**: Uses satellite imagery analysis with AI
2. **Real-time Workflow Orchestration**: n8n handles request flow
3. **Interactive Maps**: Streamlit + Folium for user interaction
4. **Scalable Deployment**: Kubernetes-native with Helm charts
5. **Multi-format Input**: Coordinates, uploaded files, or URLs
6. **Secure Storage**: MinIO with presigned URLs for results

## Contributing

See [docs/development.md](docs/development.md) for development setup and contribution guidelines.

## License

See individual component licenses in their respective directories.
