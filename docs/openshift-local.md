# OpenShift Local (CRC) Setup Guide

This guide covers setting up OpenShift Local (formerly CodeReady Containers) for testing the Flood Detection System locally.

## Overview

OpenShift Local provides a minimal OpenShift cluster on your local machine for development and testing. It's ideal for testing OpenShift-specific features before deploying to production.

## Prerequisites

### System Requirements

| Platform | CPU | Memory | Disk Space |
|----------|-----|--------|------------|
| **Minimum** | 4 vCPUs | 9 GB RAM | 35 GB |
| **Recommended** | 6+ vCPUs | 16+ GB RAM | 50+ GB |

### Important Notes

- **Resource Usage**: CRC will consume significant system resources. Close other applications during use.
- **Monthly Reset**: CRC clusters expire monthly and need to be recreated.
- **VPN Compatibility**: Some VPN solutions may conflict with CRC networking.

### Software Requirements

- **Red Hat Account**: Required for pull secret
- **Virtualization**:
  - macOS: Built-in hypervisor
  - Linux: libvirt, NetworkManager
  - Windows: Hyper-V

## Installation

### Step 1: Download CRC

1. **Get Pull Secret**:
   - Visit [Red Hat Developer Portal](https://developers.redhat.com/products/openshift-local/overview)
   - Login with your Red Hat account (free registration)
   - Download your pull secret file

2. **Download CRC Binary**:
   ```bash
   # macOS
   curl -LO https://mirror.openshift.com/pub/openshift-v4/clients/crc/latest/crc-macos-amd64.tar.xz
   tar -xf crc-macos-amd64.tar.xz
   sudo mv crc-macos-*/crc /usr/local/bin/

   # Linux
   curl -LO https://mirror.openshift.com/pub/openshift-v4/clients/crc/latest/crc-linux-amd64.tar.xz
   tar -xf crc-linux-amd64.tar.xz
   sudo mv crc-linux-*/crc /usr/local/bin/

   # Windows
   # Download and extract from the web interface
   ```

### Step 2: Setup CRC

1. **Initialize CRC**:
   ```bash
   crc setup
   ```

2. **Configure Resources** (Optional):
   ```bash
   # Increase memory allocation (recommended)
   crc config set memory 16384

   # Increase CPU allocation
   crc config set cpus 6

   # Increase disk size
   crc config set disk-size 60
   ```

3. **Start CRC**:
   ```bash
   crc start --pull-secret-file ~/Downloads/pull-secret.txt
   ```

   This will:
   - Download the OpenShift bundle (~3GB)
   - Start the virtual machine
   - Configure networking
   - Bootstrap the cluster

### Step 3: Configure CLI Access

```bash
# Set up oc CLI
eval $(crc oc-env)

# Login as administrator
oc login -u kubeadmin https://api.crc.testing:6443

# Get admin password
crc console --credentials
```

## Deployment Options

### Option 1: Quick Deployment (Recommended)

Use our automated deployment script:

```bash
# Set environment variables
export SH_CLIENT_ID="your_sentinel_hub_client_id"
export SH_CLIENT_SECRET="your_sentinel_hub_client_secret"

# Run deployment script
./openshift/scripts/deploy-openshift.sh
```

### Option 2: Manual Step-by-Step Deployment

1. **Create Project**:
   ```bash
   oc new-project flood-detection
   ```

2. **Deploy MinIO**:
   ```bash
   oc process -f openshift/templates/minio-template.yaml | oc apply -f -
   oc rollout status dc/minio
   ```

3. **Deploy Backend**:
   ```bash
   # Encode credentials
   SH_CLIENT_ID_B64=$(echo -n "$SH_CLIENT_ID" | base64)
   SH_CLIENT_SECRET_B64=$(echo -n "$SH_CLIENT_SECRET" | base64)

   oc process -f openshift/templates/backend-template.yaml \
     -p SH_CLIENT_ID_B64="$SH_CLIENT_ID_B64" \
     -p SH_CLIENT_SECRET_B64="$SH_CLIENT_SECRET_B64" \
     | oc apply -f -

   oc start-build flood-detection-backend --follow
   oc rollout status dc/flood-detection-backend
   ```

4. **Deploy n8n**:
   ```bash
   oc process -f openshift/templates/n8n-template.yaml | oc apply -f -
   oc rollout status dc/n8n
   ```

5. **Deploy Frontend**:
   ```bash
   oc process -f openshift/templates/frontend-template.yaml | oc apply -f -
   oc start-build flood-detection-frontend --follow
   oc rollout status dc/flood-detection-frontend
   ```

## Accessing Services

### Get Route URLs

```bash
# Frontend
oc get route flood-detection-frontend -o jsonpath='{.spec.host}'

# Backend
oc get route flood-detection-backend -o jsonpath='{.spec.host}'

# n8n
oc get route n8n -o jsonpath='{.spec.host}'

# MinIO Console
oc get route minio-console -o jsonpath='{.spec.host}'
```

### Default Credentials

- **n8n**: admin / admin123
- **MinIO**: minioadmin / minioadmin123

## Troubleshooting

### Common Issues

1. **CRC Won't Start**:
   ```bash
   # Check system resources
   crc config view

   # Clean up and retry
   crc delete
   crc setup
   crc start --pull-secret-file ~/Downloads/pull-secret.txt
   ```

2. **Build Failures**:
   ```bash
   # Check build logs
   oc logs bc/flood-detection-backend

   # Retry build
   oc start-build flood-detection-backend
   ```

3. **Pod Crashes**:
   ```bash
   # Check pod logs
   oc logs pod/[pod-name]

   # Check events
   oc get events --sort-by='.lastTimestamp'
   ```

4. **Network Issues**:
   ```bash
   # Check if VPN is interfering
   # Disable VPN temporarily

   # Restart CRC networking
   crc stop
   crc start
   ```

### Resource Monitoring

```bash
# Check node resources
oc adm top node

# Check pod resources
oc adm top pods

# Check persistent volumes
oc get pv
```

### Performance Optimization

1. **Increase Resources**:
   ```bash
   crc stop
   crc config set memory 20480
   crc config set cpus 8
   crc start
   ```

2. **Reduce Resource Requests**:
   ```bash
   # Edit deployment configs to use smaller resource requests
   oc patch dc/flood-detection-backend -p '{"spec":{"template":{"spec":{"containers":[{"name":"flood-detection-backend","resources":{"requests":{"memory":"1Gi","cpu":"250m"}}}]}}}}'
   ```

## Comparison: Docker Compose vs OpenShift Local

| Aspect | Docker Compose | OpenShift Local |
|--------|----------------|-----------------|
| **Setup Time** | 5-10 minutes | 30-60 minutes |
| **Resource Usage** | ~4GB RAM | ~9GB RAM minimum |
| **Networking** | Simple port mapping | Routes, ingress |
| **Storage** | Docker volumes | PersistentVolumes |
| **Security** | Basic isolation | Pod security, RBAC |
| **Monitoring** | Docker logs | OpenShift console |
| **Production Similarity** | Low | High |

## Best Practices

### Development Workflow

1. **Start with Docker Compose**:
   - Faster iteration
   - Lower resource usage
   - Good for core functionality testing

2. **Move to CRC for**:
   - OpenShift-specific testing
   - Route configuration
   - Storage class testing
   - Security policy validation

3. **Use CRC for**:
   - Final testing before production deployment
   - Troubleshooting OpenShift-specific issues
   - Validating templates and configurations

### Resource Management

```bash
# Check current usage
crc config view

# Optimize for your system
crc config set memory $(( $(sysctl -n hw.memsize) / 1024 / 1024 / 2 ))  # macOS
crc config set cpus $(nproc)  # Linux
```

### Backup and Restore

```bash
# Export project configuration
oc get all -o yaml > flood-detection-backup.yaml

# Export secrets separately
oc get secrets -o yaml > flood-detection-secrets.yaml
```

## Integration with CI/CD

### GitHub Actions Example

```yaml
name: Test on OpenShift Local
on: [push, pull_request]

jobs:
  test-openshift:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v3

    - name: Setup CRC
      run: |
        curl -LO https://mirror.openshift.com/pub/openshift-v4/clients/crc/latest/crc-linux-amd64.tar.xz
        tar -xf crc-linux-amd64.tar.xz
        sudo mv crc-linux-*/crc /usr/local/bin/

    - name: Start CRC
      run: |
        crc setup
        crc start --pull-secret-file ${{ secrets.PULL_SECRET_FILE }}

    - name: Deploy Application
      run: |
        eval $(crc oc-env)
        ./openshift/scripts/deploy-openshift.sh

    - name: Run Tests
      run: |
        # Add your test commands here
        oc get pods
```

## Cleanup

### Stop CRC

```bash
# Stop the cluster (preserves data)
crc stop

# Delete the cluster (removes all data)
crc delete

# Clean up completely
crc cleanup
```

### System Cleanup

```bash
# Remove CRC binary
sudo rm /usr/local/bin/crc

# Remove CRC configuration
rm -rf ~/.crc
```

## Next Steps

After successfully testing with OpenShift Local:

1. **Adapt for Production**:
   - Update image registry URLs
   - Configure production secrets
   - Set appropriate resource limits

2. **Deploy to Production OpenShift**:
   - Use the same templates
   - Adjust for production requirements
   - Implement monitoring and logging

3. **Set up CI/CD**:
   - Automate builds
   - Implement testing pipelines
   - Configure deployment automation

For production deployment guidance, see [deployment.md](./deployment.md).