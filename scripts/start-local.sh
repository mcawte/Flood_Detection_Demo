#!/bin/bash

# Local Development Startup Script for Flood Detection System
# This script starts the system using Docker Compose for local development

set -e

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Function to check prerequisites
check_prerequisites() {
    print_status "Checking prerequisites..."

    if ! command_exists docker; then
        print_error "Docker is not installed"
        print_status "Please install Docker from https://docs.docker.com/get-docker/"
        exit 1
    fi

    if ! command_exists docker-compose; then
        print_error "Docker Compose is not installed"
        print_status "Please install Docker Compose from https://docs.docker.com/compose/install/"
        exit 1
    fi

    # Check if Docker is running
    if ! docker info &>/dev/null; then
        print_error "Docker is not running"
        print_status "Please start Docker and try again"
        exit 1
    fi

    print_success "Prerequisites check passed"
}

# Function to setup environment
setup_environment() {
    print_status "Setting up environment..."

    # Check if .env file exists
    if [[ ! -f .env ]]; then
        if [[ -f .env.example ]]; then
            print_status "Creating .env file from template..."
            cp .env.example .env
            print_warning "Please edit .env file with your credentials before continuing"
            print_status "Required credentials:"
            echo "  - SH_CLIENT_ID: Sentinel Hub Client ID"
            echo "  - SH_CLIENT_SECRET: Sentinel Hub Client Secret"
            echo ""
            read -p "Press Enter to continue after editing .env file..."
        else
            print_error ".env.example file not found"
            exit 1
        fi
    fi

    # Source environment variables
    if [[ -f .env ]]; then
        export $(cat .env | grep -v '^#' | xargs)
        print_success "Environment variables loaded"
    fi

    # Validate required environment variables
    if [[ -z "$SH_CLIENT_ID" ]]; then
        print_warning "SH_CLIENT_ID not set in .env file"
        print_status "The system will work for local file uploads, but Sentinel Hub features will be disabled"
    fi

    if [[ -z "$SH_CLIENT_SECRET" ]]; then
        print_warning "SH_CLIENT_SECRET not set in .env file"
        print_status "The system will work for local file uploads, but Sentinel Hub features will be disabled"
    fi
}

# Function to cleanup existing containers
cleanup_containers() {
    print_status "Cleaning up existing containers..."

    if docker-compose ps -q | grep -q .; then
        print_status "Stopping existing containers..."
        docker-compose down
    fi

    # Remove any orphaned containers
    docker container prune -f >/dev/null 2>&1 || true

    print_success "Cleanup completed"
}

# Function to start services
start_services() {
    print_status "Starting Flood Detection System..."

    # Pull latest images
    print_status "Pulling latest images..."
    docker-compose pull

    # Build local images
    print_status "Building local images..."
    docker-compose build --no-cache

    # Start services
    print_status "Starting all services..."
    docker-compose up -d

    print_success "All services started"
}

# Function to wait for services to be ready
wait_for_services() {
    print_status "Waiting for services to be ready..."

    # Wait for MinIO
    print_status "Waiting for MinIO..."
    while ! docker-compose exec minio curl -f http://localhost:9000/minio/health/live >/dev/null 2>&1; do
        sleep 2
        echo -n "."
    done
    echo
    print_success "MinIO is ready"

    # Wait for backend
    print_status "Waiting for backend..."
    timeout=180
    elapsed=0
    while ! curl -f http://localhost:8080/health >/dev/null 2>&1; do
        if [ $elapsed -ge $timeout ]; then
            print_warning "Backend health check timeout, but continuing..."
            break
        fi
        sleep 5
        elapsed=$((elapsed + 5))
        echo -n "."
    done
    echo
    print_success "Backend is ready (or timeout reached)"

    # Wait for frontend
    print_status "Waiting for frontend..."
    timeout=120
    elapsed=0
    while ! curl -f http://localhost:8501/_stcore/health >/dev/null 2>&1; do
        if [ $elapsed -ge $timeout ]; then
            print_warning "Frontend health check timeout, but continuing..."
            break
        fi
        sleep 5
        elapsed=$((elapsed + 5))
        echo -n "."
    done
    echo
    print_success "Frontend is ready (or timeout reached)"

    # Wait for n8n
    print_status "Waiting for n8n..."
    timeout=120
    elapsed=0
    while ! curl -f http://localhost:5678/healthz >/dev/null 2>&1; do
        if [ $elapsed -ge $timeout ]; then
            print_warning "n8n health check timeout, but continuing..."
            break
        fi
        sleep 5
        elapsed=$((elapsed + 5))
        echo -n "."
    done
    echo
    print_success "n8n is ready (or timeout reached)"
}

# Function to display access information
show_access_info() {
    print_success "Flood Detection System is now running!"
    echo
    print_status "Access URLs:"
    echo -e "${GREEN}Frontend (Streamlit):${NC} http://localhost:8501"
    echo -e "${GREEN}Backend API:${NC} http://localhost:8080"
    echo -e "${GREEN}n8n Workflows:${NC} http://localhost:5678"
    echo -e "  ${YELLOW}Username:${NC} admin"
    echo -e "  ${YELLOW}Password:${NC} admin123"
    echo -e "${GREEN}MinIO Console:${NC} http://localhost:9000"
    echo -e "  ${YELLOW}Username:${NC} minioadmin"
    echo -e "  ${YELLOW}Password:${NC} minioadmin123"
    echo
    print_status "Quick Test:"
    echo "1. Open the frontend at http://localhost:8501"
    echo "2. Try the 'From File Upload' tab to test with a GeoTIFF file"
    echo "3. Or use 'From Coordinates and Date' tab (requires Sentinel Hub credentials)"
    echo
    print_status "To view logs:"
    echo "  docker-compose logs -f [service-name]"
    echo "  Services: flood-backend, flood-frontend, n8n, minio"
    echo
    print_status "To stop the system:"
    echo "  docker-compose down"
    echo
    print_status "To stop and remove all data:"
    echo "  docker-compose down -v"
}

# Function to show status
show_status() {
    print_status "Service Status:"
    docker-compose ps
    echo

    print_status "Health Checks:"

    # MinIO health
    if curl -f http://localhost:9000/minio/health/live >/dev/null 2>&1; then
        echo -e "${GREEN}✓${NC} MinIO: Healthy"
    else
        echo -e "${RED}✗${NC} MinIO: Not responding"
    fi

    # Backend health
    if curl -f http://localhost:8080/health >/dev/null 2>&1; then
        echo -e "${GREEN}✓${NC} Backend: Healthy"
    else
        echo -e "${RED}✗${NC} Backend: Not responding"
    fi

    # Frontend health
    if curl -f http://localhost:8501/_stcore/health >/dev/null 2>&1; then
        echo -e "${GREEN}✓${NC} Frontend: Healthy"
    else
        echo -e "${RED}✗${NC} Frontend: Not responding"
    fi

    # n8n health
    if curl -f http://localhost:5678/healthz >/dev/null 2>&1; then
        echo -e "${GREEN}✓${NC} n8n: Healthy"
    else
        echo -e "${RED}✗${NC} n8n: Not responding"
    fi
}

# Main function
main() {
    print_status "Starting Flood Detection System for local development..."

    check_prerequisites
    setup_environment
    cleanup_containers
    start_services
    wait_for_services
    show_access_info
}

# Handle script arguments
case "${1:-}" in
    "start")
        main
        ;;
    "stop")
        print_status "Stopping Flood Detection System..."
        docker-compose down
        print_success "System stopped"
        ;;
    "restart")
        print_status "Restarting Flood Detection System..."
        docker-compose down
        main
        ;;
    "status")
        show_status
        ;;
    "logs")
        if [[ -n "${2:-}" ]]; then
            docker-compose logs -f "$2"
        else
            docker-compose logs -f
        fi
        ;;
    "clean")
        print_warning "This will stop all services and remove all data"
        read -p "Are you sure? (y/N): " confirm
        if [[ $confirm == [yY] ]]; then
            docker-compose down -v
            docker system prune -f
            print_success "System cleaned"
        fi
        ;;
    "")
        main
        ;;
    *)
        echo "Usage: $0 [start|stop|restart|status|logs [service]|clean]"
        echo "  start (default): Start the system"
        echo "  stop: Stop the system"
        echo "  restart: Restart the system"
        echo "  status: Show service status"
        echo "  logs [service]: Show logs (optionally for specific service)"
        echo "  clean: Stop and remove all data"
        exit 1
        ;;
esac