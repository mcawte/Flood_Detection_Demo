# Deployment Guide

This guide covers deploying the Flood Detection System to Kubernetes clusters.

## Prerequisites

### Required Tools
- Kubernetes cluster (1.20+)
- Helm 3.8+
- kubectl configured
- Docker (for building images)

### Required Credentials
```bash
# Sentinel Hub API (for satellite data access)
export SH_CLIENT_ID="your_sentinel_hub_client_id"
export SH_CLIENT_SECRET="your_sentinel_hub_client_secret"

# MinIO (object storage credentials)
export MINIO_ACCESS_KEY="your_minio_access_key"
export MINIO_SECRET_KEY="your_minio_secret_key"

# OpenRouteService (routing for Streamlit frontend)
export ORS_API_KEY="your_openrouteservice_api_key"
```

## Local Development Deployment

### Using Docker Compose

1. **Set environment variables**:
   ```bash
   cp .env.example .env
   # Edit .env with your credentials
   ```

2. **Start services**:
   ```bash
   docker-compose up -d
   ```

3. **Access services**:
   - Frontend: http://localhost:8501
   - Backend: http://localhost:8080
   - n8n: http://localhost:5678 (admin/admin123)
   - MinIO: http://localhost:9000 (minioadmin/minioadmin123)

4. **Workflow import**: the n8n container automatically activates any JSON files mounted in `./n8n-workflows/`, so no manual import is needed. Check http://localhost:5678 (admin/admin123) to confirm the workflow is active.

## Kubernetes Deployment

### Option 1: Complete System Deployment

Deploy all components with a single umbrella chart:

```bash
# Create namespace
kubectl create namespace flood-detection

# Install the complete system
helm install flood-detection ./charts/flood-detection-system \
  --namespace flood-detection \
  --set secrets.sentinelHub.clientId="$SH_CLIENT_ID" \
  --set secrets.sentinelHub.clientSecret="$SH_CLIENT_SECRET" \
  --set secrets.minio.accessKey="$MINIO_ACCESS_KEY" \
  --set secrets.minio.secretKey="$MINIO_SECRET_KEY"
```

### Option 2: Component-by-Component Deployment

Deploy each service individually for more control:

1. **Deploy MinIO (object storage)**:
   ```bash
   helm install minio ./charts/minio \
     --namespace flood-detection \
     --set auth.rootUser="$MINIO_ACCESS_KEY" \
     --set auth.rootPassword="$MINIO_SECRET_KEY"
   ```

2. **Deploy Backend (inference service)**:
   ```bash
   helm install backend ./charts/flood-detection-backend \
     --namespace flood-detection \
     --set secrets.sentinelHub.clientId="$SH_CLIENT_ID" \
     --set secrets.sentinelHub.clientSecret="$SH_CLIENT_SECRET" \
     --set secrets.minio.accessKey="$MINIO_ACCESS_KEY" \
     --set secrets.minio.secretKey="$MINIO_SECRET_KEY"
   ```

3. **Deploy n8n (workflow engine)**:
   ```bash
   helm install n8n ./charts/n8n \
     --namespace flood-detection
   ```

4. **Deploy Frontend (Streamlit app)**:
   ```bash
   helm install frontend ./charts/flood-detection-frontend \
     --namespace flood-detection
   ```

### Verify Deployment

```bash
# Check pod status
kubectl get pods -n flood-detection

# Check services
kubectl get services -n flood-detection

# Check ingress (if enabled)
kubectl get ingress -n flood-detection

# View logs
kubectl logs -f deployment/flood-detection-backend -n flood-detection
```

## Production Configuration

### Resource Requirements

| Component | CPU Request | Memory Request | CPU Limit | Memory Limit |
|-----------|-------------|----------------|-----------|--------------|
| Backend   | 500m        | 2Gi           | 2000m     | 4Gi          |
| Frontend  | 200m        | 512Mi         | 500m      | 1Gi          |
| n8n       | 200m        | 512Mi         | 500m      | 1Gi          |
| MinIO     | 200m        | 512Mi         | 500m      | 1Gi          |

### Storage Requirements

- **Backend Models**: 5Gi PVC for model files
- **Backend Configs**: 1Gi PVC for configuration
- **n8n Data**: 1Gi PVC for workflows and data
- **MinIO Data**: 10Gi+ PVC for object storage

### Ingress Configuration

```yaml
# values.yaml snippet
ingress:
  enabled: true
  className: "nginx"
  annotations:
    cert-manager.io/cluster-issuer: "letsencrypt-prod"
    nginx.ingress.kubernetes.io/proxy-body-size: "50m"
  hosts:
    - host: flood-detection.yourdomain.com
      paths:
        - path: /
          pathType: Prefix
          service: flood-detection-frontend
        - path: /api
          pathType: Prefix
          service: flood-detection-backend
  tls:
    - secretName: flood-detection-tls
      hosts:
        - flood-detection.yourdomain.com
```

### Security Considerations

1. **Secrets Management**:
   ```bash
   # Use external secret management
   kubectl create secret generic flood-secrets \
     --from-literal=sh-client-id="$SH_CLIENT_ID" \
     --from-literal=sh-client-secret="$SH_CLIENT_SECRET" \
     --namespace flood-detection
   ```

2. **Network Policies**:
   ```yaml
   # Restrict pod-to-pod communication
   apiVersion: networking.k8s.io/v1
   kind: NetworkPolicy
   metadata:
     name: flood-detection-netpol
   spec:
     podSelector:
       matchLabels:
         app.kubernetes.io/part-of: flood-detection
     policyTypes:
     - Ingress
     - Egress
   ```

3. **Pod Security Standards**:
   ```yaml
   # Apply restricted pod security
   apiVersion: v1
   kind: Namespace
   metadata:
     name: flood-detection
     labels:
       pod-security.kubernetes.io/enforce: restricted
   ```

## Monitoring and Observability

### Health Checks

All services include health check endpoints:
- Backend: `GET /health`
- Frontend: `GET /_stcore/health`
- n8n: `GET /healthz`
- MinIO: `GET /minio/health/live`

### Metrics Collection

Enable Prometheus metrics:

```yaml
# values.yaml
monitoring:
  enabled: true
  prometheus:
    enabled: true
    serviceMonitor:
      enabled: true
```

### Log Aggregation

Configure log forwarding to your logging system:

```yaml
# Fluent Bit configuration
apiVersion: v1
kind: ConfigMap
metadata:
  name: fluent-bit-config
data:
  fluent-bit.conf: |
    [INPUT]
        Name tail
        Path /var/log/containers/*flood-detection*.log
        Parser kubernetes
```

## Troubleshooting

### Common Issues

1. **Backend model download fails**:
   ```bash
   # Check MinIO connectivity
   kubectl exec -it deployment/flood-detection-backend -- \
     curl http://minio:9000/minio/health/live
   ```

2. **Frontend can't connect to backend**:
   ```bash
   # Test service connectivity
   kubectl exec -it deployment/flood-detection-frontend -- \
     curl http://flood-detection-backend:8080/health
   ```

3. **n8n workflows not loading**:
   ```bash
   # Check n8n logs
   kubectl logs deployment/n8n -n flood-detection

   # Verify workflow files
   kubectl exec -it deployment/n8n -- ls -la /workflows/
   ```

### Log Analysis

```bash
# View all component logs
kubectl logs -l app.kubernetes.io/part-of=flood-detection -n flood-detection

# Stream logs in real-time
kubectl logs -f deployment/flood-detection-backend -n flood-detection

# Check events
kubectl get events -n flood-detection --sort-by='.lastTimestamp'
```

## Scaling

### Horizontal Pod Autoscaling

```yaml
# Enable HPA for backend
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: flood-detection-backend-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: flood-detection-backend
  minReplicas: 1
  maxReplicas: 5
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
```

### Resource Optimization

Monitor resource usage and adjust:

```bash
# Check resource usage
kubectl top pods -n flood-detection
kubectl top nodes

# Adjust resource requests/limits
helm upgrade flood-detection ./charts/flood-detection-system \
  --namespace flood-detection \
  --set flood-detection-backend.resources.requests.cpu=1000m
```

## Updates and Rollbacks

### Updating Components

```bash
# Update specific component
helm upgrade backend ./charts/flood-detection-backend \
  --namespace flood-detection

# Update entire system
helm upgrade flood-detection ./charts/flood-detection-system \
  --namespace flood-detection
```

### Rollback

```bash
# View release history
helm history flood-detection -n flood-detection

# Rollback to previous version
helm rollback flood-detection 1 -n flood-detection
```

## Backup and Recovery

### Database Backup

```bash
# Backup n8n database
kubectl exec deployment/n8n -n flood-detection -- \
  sqlite3 /home/node/.n8n/database.sqlite ".backup /tmp/n8n-backup.db"

kubectl cp flood-detection/n8n-pod:/tmp/n8n-backup.db ./n8n-backup.db
```

### MinIO Data Backup

```bash
# Use MinIO client for backup
kubectl port-forward service/minio 9000:9000 -n flood-detection &
mc mirror myminio/flood-predictions ./backup/flood-predictions/
mc mirror myminio/flood-models ./backup/flood-models/
```

For more detailed information, see:
- [Development Guide](./development.md)
- [API Documentation](./api.md)
