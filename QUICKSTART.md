# Quick Start Guide

Get the Flood Detection System running locally in under 10 minutes!

## 🚀 Option 1: Docker Compose (Fastest)

### Prerequisites
- Docker & Docker Compose installed
- 4GB+ RAM available
- 10GB+ disk space

### Steps

1. **Clone and setup**:
   ```bash
   git clone <repository-url>
   cd flood-detection-demo

   # Create environment file
   cp .env.example .env
   ```

2. **Add your credentials** (edit `.env`):
   ```bash
   # Required for satellite imagery (optional for local testing)
   SH_CLIENT_ID=your_sentinel_hub_client_id
   SH_CLIENT_SECRET=your_sentinel_hub_client_secret
   ```

3. **Start the system**:
   ```bash
   ./scripts/start-local.sh
   ```

4. **Access the system**:
   - **Frontend**: http://localhost:8501
   - **Backend API**: http://localhost:8080
   - **n8n Workflows**: http://localhost:5678 (admin/admin123)
   - **MinIO Console**: http://localhost:9000 (minioadmin/minioadmin123)

### Testing
- Go to http://localhost:8501
- Try the "From File Upload" tab with any GeoTIFF file
- Or use "From Coordinates and Date" if you have Sentinel Hub credentials

---

## ☸️ Option 2: OpenShift Local (CRC)

### Prerequisites
- 9GB+ RAM available
- 35GB+ disk space
- Red Hat Developer account (free)

### Steps

1. **Download pull secret**:
   - Visit [Red Hat Developer Portal](https://developers.redhat.com/products/openshift-local/overview)
   - Download pull secret to `~/Downloads/pull-secret.txt`

2. **Install CRC**:
   ```bash
   # macOS
   curl -LO https://mirror.openshift.com/pub/openshift-v4/clients/crc/latest/crc-macos-amd64.tar.xz
   tar -xf crc-macos-amd64.tar.xz
   sudo mv crc-macos-*/crc /usr/local/bin/

   # Linux
   curl -LO https://mirror.openshift.com/pub/openshift-v4/clients/crc/latest/crc-linux-amd64.tar.xz
   tar -xf crc-linux-amd64.tar.xz
   sudo mv crc-linux-*/crc /usr/local/bin/
   ```

3. **Setup and start CRC**:
   ```bash
   crc setup
   crc config set memory 16384  # Optional: increase memory
   crc start --pull-secret-file ~/Downloads/pull-secret.txt
   ```

4. **Deploy the system**:
   ```bash
   # Clone repository
   git clone <repository-url>
   cd flood-detection-demo

   # Set environment variables
   export SH_CLIENT_ID="your_sentinel_hub_client_id"
   export SH_CLIENT_SECRET="your_sentinel_hub_client_secret"

   # Deploy
   ./openshift/scripts/deploy-openshift.sh
   ```

5. **Access via OpenShift routes** (URLs provided by deployment script)

---

## 🧪 Quick Test Scenarios

### Test 1: File Upload (No credentials needed)
1. Open frontend URL
2. Go to "From File Upload" tab
3. Upload any GeoTIFF file
4. Wait for processing
5. Get result URL from MinIO

### Test 2: Coordinate-based Detection (Needs Sentinel Hub)
1. Open frontend URL
2. Go to "From Coordinates and Date" tab
3. Enter coordinates (e.g., "-1.57, 53.80, -1.50, 53.83")
4. Select date
5. Submit for processing

### Test 3: n8n Workflow
1. Access n8n interface
2. Import flood detection workflow
3. Test webhook endpoint
4. Monitor workflow execution

---

## 🛠️ Management Commands

### Docker Compose
```bash
# Start system
./scripts/start-local.sh

# Stop system
./scripts/start-local.sh stop

# View logs
./scripts/start-local.sh logs [service-name]

# Check status
./scripts/start-local.sh status

# Clean up everything
./scripts/start-local.sh clean
```

### OpenShift
```bash
# Deploy individual components
./openshift/scripts/deploy-openshift.sh minio
./openshift/scripts/deploy-openshift.sh backend
./openshift/scripts/deploy-openshift.sh n8n
./openshift/scripts/deploy-openshift.sh frontend

# Check status
oc get pods
oc get routes

# View logs
oc logs -f dc/flood-detection-backend

# Clean up
./openshift/scripts/deploy-openshift.sh clean
```

---

## 🔧 Troubleshooting

### Docker Compose Issues

**Port conflicts**:
```bash
# Check what's using ports
lsof -i :8080
lsof -i :8501

# Stop conflicting services or change ports in docker-compose.yml
```

**Out of memory**:
```bash
# Check Docker resources
docker system df
docker system prune  # Clean up
```

**Backend not starting**:
```bash
# Check logs
docker-compose logs flood-backend

# Common issue: missing model files (will download automatically)
```

### OpenShift Issues

**CRC won't start**:
```bash
# Clean and restart
crc delete
crc setup
crc start --pull-secret-file ~/Downloads/pull-secret.txt
```

**Build failures**:
```bash
# Check build logs
oc logs bc/flood-detection-backend

# Retry build
oc start-build flood-detection-backend
```

**Pod crashes**:
```bash
# Check pod logs
oc logs pod-name

# Check events
oc get events --sort-by='.lastTimestamp'
```

---

## 🎯 Next Steps

Once you have the system running:

1. **Configure Sentinel Hub**:
   - Get free account at [Sentinel Hub](https://www.sentinel-hub.com/)
   - Add credentials to enable satellite imagery

2. **Customize Workflows**:
   - Edit n8n workflows for your use case
   - Add email notifications
   - Integrate with external systems

3. **Scale for Production**:
   - See [deployment.md](docs/deployment.md) for production setup
   - Configure monitoring and logging
   - Set up CI/CD pipelines

4. **Extend the System**:
   - Add new AI models
   - Integrate additional data sources
   - Build custom frontend components

---

## 📚 Documentation

- **[Development Guide](docs/development.md)**: Set up development environment
- **[Deployment Guide](docs/deployment.md)**: Production deployment
- **[OpenShift Local Guide](docs/openshift-local.md)**: Detailed CRC setup
- **[API Documentation](docs/api.md)**: API reference

---

## 🆘 Support

Having issues? Check:

1. **Logs**: Always check service logs first
2. **Prerequisites**: Ensure system requirements are met
3. **Network**: VPNs can interfere with networking
4. **Resources**: Ensure enough RAM/CPU/disk space
5. **Credentials**: Verify API keys are correct

For specific errors, check the troubleshooting sections in the detailed documentation.