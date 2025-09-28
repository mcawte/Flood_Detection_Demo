# Development Guide

This guide covers setting up the development environment and contributing to the Flood Detection System.

## Development Environment Setup

### Prerequisites

- Python 3.11+
- Node.js 18+ (for n8n development)
- Docker and Docker Compose
- Git
- VS Code or preferred IDE

### Local Setup

1. **Clone the repository**:
   ```bash
   git clone <repository-url>
   cd flood-detection-demo
   ```

2. **Create environment file**:
   ```bash
   cp .env.example .env
   # Edit .env with your development credentials
   ```

3. **Start development environment**:
   ```bash
   docker-compose up -d
   ```

## Component Development

### Backend Development (Python)

1. **Set up Python environment**:
   ```bash
   cd flood-detection-backend
   python -m venv venv
   source venv/bin/activate  # Linux/Mac
   # or
   venv\Scripts\activate     # Windows

   pip install -r requirements.txt
   ```

2. **Environment variables**:
   ```bash
   export MINIO_ENDPOINT="http://localhost:9000"
   export MINIO_ACCESS_KEY="minioadmin"
   export MINIO_SECRET_KEY="minioadmin123"
   export SH_CLIENT_ID="your_sentinel_hub_client_id"
   export SH_CLIENT_SECRET="your_sentinel_hub_client_secret"
   export PYTHONPATH="/path/to/flood-detection-backend"
   ```

3. **Run backend locally**:
   ```bash
   cd app
   python mcp_server.py
   ```

4. **Testing**:
   ```bash
   # Run tests
   pytest test/

   # Run with coverage
   pytest --cov=app test/
   ```

### Frontend Development (Streamlit)

1. **Set up Python environment**:
   ```bash
   cd flood-detection-frontend
   python -m venv venv
   source venv/bin/activate

   pip install -r requirements.txt
   ```

2. **Environment variables**:
   ```bash
   export N8N_WEBHOOK_URL="http://localhost:5678/webhook/flood-detection"
   export BACKEND_MCP_URL="http://localhost:8080"
    export ORS_API_KEY="your_openrouteservice_api_key"
   ```

3. **Run frontend locally**:
   ```bash
   streamlit run app.py
   ```

4. **Development tips**:
   ```bash
   # Auto-reload on file changes
   streamlit run app.py --server.runOnSave=true

   # Different port
   streamlit run app.py --server.port=8502
   ```

### n8n Workflow Development

1. **Access n8n interface**:
   - URL: http://localhost:5678
   - Username: admin
   - Password: admin123

2. **Import workflows**: restart the `flood-n8n` container after editing JSON files under `n8n-workflows/`; startup scripts automatically import and activate them. For quick reload without a full stack restart you can run:
   ```bash
   docker compose restart n8n
   ```

3. **Workflow development**:
   - Use the web interface to create/edit workflows
   - Export workflows as JSON files
   - Store in `n8n-workflows/` directory

## Code Style and Standards

### Python Code Style

We follow PEP 8 with these tools:

```bash
# Install development tools
pip install black isort flake8 mypy

# Format code
black .
isort .

# Lint code
flake8 .

# Type checking
mypy app/
```

### Pre-commit Hooks

Set up pre-commit hooks:

```bash
pip install pre-commit
pre-commit install

# Run manually
pre-commit run --all-files
```

### Configuration Files

**.pre-commit-config.yaml**:
```yaml
repos:
  - repo: https://github.com/psf/black
    rev: 22.3.0
    hooks:
      - id: black
  - repo: https://github.com/pycqa/isort
    rev: 5.10.1
    hooks:
      - id: isort
  - repo: https://github.com/pycqa/flake8
    rev: 4.0.1
    hooks:
      - id: flake8
```

## Testing

### Backend Testing

```bash
cd flood-detection-backend

# Unit tests
pytest app/test/ -v

# Integration tests
pytest app/test/integration/ -v

# Coverage report
pytest --cov=app --cov-report=html test/
```

### Frontend Testing

```bash
cd flood-detection-frontend

# Streamlit app testing
pytest test/ -v

# UI testing with selenium
pytest test/ui/ -v
```

### End-to-End Testing

```bash
# Start all services
docker-compose up -d

# Run E2E tests
pytest e2e-tests/ -v
```

## Building and Deployment

### Building Docker Images

```bash
# Build backend image
docker build -t flood-detection-backend:dev ./flood-detection-backend/

# Build frontend image
docker build -t flood-detection-frontend:dev ./flood-detection-frontend/

# Build all images
docker-compose build
```

### Local Kubernetes Testing

```bash
# Use kind or minikube
kind create cluster --name flood-detection

# Load local images
kind load docker-image flood-detection-backend:dev --name flood-detection
kind load docker-image flood-detection-frontend:dev --name flood-detection

# Deploy to local cluster
helm install flood-detection ./charts/flood-detection-system \
  --set flood-detection-backend.image.tag=dev \
  --set flood-detection-frontend.image.tag=dev
```

## Debugging

### Backend Debugging

```bash
# Enable debug logging
export LOG_LEVEL=DEBUG

# Run with debugger
python -m pdb app/mcp_server.py
```

### VS Code Debug Configuration

**.vscode/launch.json**:
```json
{
  "version": "0.2.0",
  "configurations": [
    {
      "name": "Debug Backend",
      "type": "python",
      "request": "launch",
      "program": "${workspaceFolder}/flood-detection-backend/app/mcp_server.py",
      "env": {
        "PYTHONPATH": "${workspaceFolder}/flood-detection-backend",
        "MINIO_ENDPOINT": "http://localhost:9000"
      },
      "console": "integratedTerminal"
    },
    {
      "name": "Debug Frontend",
      "type": "python",
      "request": "launch",
      "module": "streamlit",
      "args": ["run", "app.py"],
      "env": {
        "N8N_WEBHOOK_URL": "http://localhost:5678/webhook/flood-detection"
      },
      "cwd": "${workspaceFolder}/flood-detection-frontend"
    }
  ]
}
```

### Container Debugging

```bash
# Access backend container
docker exec -it flood-backend bash

# Access frontend container
docker exec -it flood-frontend bash

# View logs
docker logs -f flood-backend
docker logs -f flood-frontend
```

## Performance Profiling

### Backend Profiling

```bash
# Install profiling tools
pip install py-spy memory-profiler

# CPU profiling
py-spy record -o profile.svg -- python app/mcp_server.py

# Memory profiling
mprof run python app/mcp_server.py
mprof plot
```

### Load Testing

```bash
# Install load testing tools
pip install locust

# Run load tests
locust -f load_tests/backend_load_test.py --host=http://localhost:8080
```

## Database Management

### n8n Database

```bash
# Access SQLite database
docker exec -it flood-n8n sqlite3 /home/node/.n8n/database.sqlite

# Backup database
docker exec flood-n8n sqlite3 /home/node/.n8n/database.sqlite ".backup /tmp/backup.db"
docker cp flood-n8n:/tmp/backup.db ./n8n-backup.db

# Restore database
docker cp ./n8n-backup.db flood-n8n:/tmp/restore.db
docker exec flood-n8n sqlite3 /home/node/.n8n/database.sqlite ".restore /tmp/restore.db"
```

## Contributing

### Git Workflow

1. **Create feature branch**:
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Make changes and commit**:
   ```bash
   git add .
   git commit -m "feat: add your feature description"
   ```

3. **Push and create PR**:
   ```bash
   git push origin feature/your-feature-name
   # Create pull request through GitHub interface
   ```

### Commit Message Format

Follow conventional commits:

```
type(scope): description

[optional body]

[optional footer]
```

Types:
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `style`: Code style changes
- `refactor`: Code refactoring
- `test`: Test changes
- `chore`: Build/tool changes

### Code Review Process

1. All changes require PR review
2. Tests must pass
3. Code coverage should not decrease
4. Documentation must be updated
5. Security considerations reviewed

## Troubleshooting

### Common Development Issues

1. **Port conflicts**:
   ```bash
   # Check port usage
   lsof -i :8080
   lsof -i :8501

   # Use different ports
   docker-compose up -d --scale backend=0
   python app/mcp_server.py --port 8081
   ```

2. **Permission issues**:
   ```bash
   # Fix Docker volume permissions
   sudo chown -R $USER:$USER ./data/

   # Fix Python package permissions
   chmod +x scripts/*.sh
   ```

3. **Environment variable issues**:
   ```bash
   # Check environment
   env | grep MINIO
   env | grep SH_

   # Source environment file
   set -a && source .env && set +a
   ```

### Getting Help

- Check existing issues in the repository
- Review logs for error messages
- Join the development discussion
- Create new issues with detailed reproduction steps

## Release Process

### Version Management

```bash
# Update version in all files
scripts/update-version.sh 1.1.0

# Tag release
git tag -a v1.1.0 -m "Release version 1.1.0"
git push origin v1.1.0
```

### Release Checklist

- [ ] All tests passing
- [ ] Documentation updated
- [ ] Version numbers updated
- [ ] Docker images built and tagged
- [ ] Helm charts updated
- [ ] Security scan completed
- [ ] Performance benchmarks run
- [ ] Release notes prepared
