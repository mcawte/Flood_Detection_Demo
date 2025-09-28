#!/bin/bash

# OpenShift Deployment Script for Flood Detection System
# This script deploys the complete flood detection system to OpenShift

set -e

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
PROJECT_NAME="flood-detection"
TEMPLATES_DIR="$(dirname "$0")/../templates"
GIT_REPO_URL="https://github.com/mcawte/flood_detection_demo.git"
GIT_REF="main"

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

# Function to encode base64
base64_encode() {
    echo -n "$1" | base64 | tr -d '\n'
}

# Function to check prerequisites
check_prerequisites() {
    print_status "Checking prerequisites..."

    if ! command_exists oc; then
        print_error "OpenShift CLI 'oc' is not installed"
        exit 1
    fi

    if ! oc whoami &>/dev/null; then
        print_error "Not logged into OpenShift cluster"
        print_status "Please run: oc login <cluster-url>"
        exit 1
    fi

    print_success "Prerequisites check passed"
}

# Function to read environment variables
read_credentials() {
    print_status "Reading credentials..."

    # Check for required environment variables
    if [[ -z "$SH_CLIENT_ID" ]]; then
        read -p "Enter Sentinel Hub Client ID: " SH_CLIENT_ID
    fi

    if [[ -z "$SH_CLIENT_SECRET" ]]; then
        read -s -p "Enter Sentinel Hub Client Secret: " SH_CLIENT_SECRET
        echo
    fi

    # Set default values for optional variables
    MINIO_ACCESS_KEY=${MINIO_ACCESS_KEY:-"minioadmin"}
    MINIO_SECRET_KEY=${MINIO_SECRET_KEY:-"minioadmin123"}
    N8N_BASIC_AUTH_USER=${N8N_BASIC_AUTH_USER:-"admin"}
    N8N_BASIC_AUTH_PASSWORD=${N8N_BASIC_AUTH_PASSWORD:-"admin123"}

    # Encode credentials to base64
    SH_CLIENT_ID_B64=$(base64_encode "$SH_CLIENT_ID")
    SH_CLIENT_SECRET_B64=$(base64_encode "$SH_CLIENT_SECRET")
    MINIO_ACCESS_KEY_B64=$(base64_encode "$MINIO_ACCESS_KEY")
    MINIO_SECRET_KEY_B64=$(base64_encode "$MINIO_SECRET_KEY")
    N8N_BASIC_AUTH_USER_B64=$(base64_encode "$N8N_BASIC_AUTH_USER")
    N8N_BASIC_AUTH_PASSWORD_B64=$(base64_encode "$N8N_BASIC_AUTH_PASSWORD")

    print_success "Credentials loaded"
}

# Function to create or switch to project
setup_project() {
    print_status "Setting up OpenShift project: $PROJECT_NAME"

    if oc get project "$PROJECT_NAME" &>/dev/null; then
        print_warning "Project $PROJECT_NAME already exists, switching to it"
        oc project "$PROJECT_NAME"
    else
        print_status "Creating new project: $PROJECT_NAME"
        oc new-project "$PROJECT_NAME" \
            --display-name="Flood Detection System" \
            --description="AI-powered flood detection with Streamlit frontend and n8n workflows"
    fi

    print_success "Project setup completed"
}

# Function to deploy MinIO
deploy_minio() {
    print_status "Deploying MinIO object storage..."

    oc process -f "$TEMPLATES_DIR/minio-template.yaml" \
        -p MINIO_ROOT_USER_B64="$MINIO_ACCESS_KEY_B64" \
        -p MINIO_ROOT_PASSWORD_B64="$MINIO_SECRET_KEY_B64" \
        | oc apply -f -

    print_status "Waiting for MinIO to be ready..."
    oc rollout status dc/minio --timeout=300s

    print_success "MinIO deployed successfully"
}

# Function to deploy backend
deploy_backend() {
    print_status "Deploying flood detection backend..."

    # Get MinIO service URL
    MINIO_ENDPOINT="http://minio:9000"

    oc process -f "$TEMPLATES_DIR/backend-template.yaml" \
        -p GIT_REPO_URL="$GIT_REPO_URL" \
        -p GIT_REF="$GIT_REF" \
        -p MINIO_ENDPOINT="$MINIO_ENDPOINT" \
        -p MINIO_ACCESS_KEY_B64="$MINIO_ACCESS_KEY_B64" \
        -p MINIO_SECRET_KEY_B64="$MINIO_SECRET_KEY_B64" \
        -p SH_CLIENT_ID_B64="$SH_CLIENT_ID_B64" \
        -p SH_CLIENT_SECRET_B64="$SH_CLIENT_SECRET_B64" \
        | oc apply -f -

    print_status "Starting backend build..."
    oc start-build flood-detection-backend --follow

    print_status "Waiting for backend to be ready..."
    oc rollout status dc/flood-detection-backend --timeout=600s

    print_success "Backend deployed successfully"
}

# Function to deploy n8n
deploy_n8n() {
    print_status "Deploying n8n workflow engine..."

    # Get cluster subdomain for webhook URL
    CLUSTER_SUBDOMAIN=$(oc get route -n openshift-console console -o jsonpath='{.spec.host}' | sed 's/console-openshift-console.//')
    WEBHOOK_URL="https://n8n-${PROJECT_NAME}.${CLUSTER_SUBDOMAIN}/"

    oc process -f "$TEMPLATES_DIR/n8n-template.yaml" \
        -p N8N_BASIC_AUTH_USER_B64="$N8N_BASIC_AUTH_USER_B64" \
        -p N8N_BASIC_AUTH_PASSWORD_B64="$N8N_BASIC_AUTH_PASSWORD_B64" \
        -p WEBHOOK_URL="$WEBHOOK_URL" \
        | oc apply -f -

    print_status "Waiting for n8n to be ready..."
    oc rollout status dc/n8n --timeout=300s

    print_success "n8n deployed successfully"
}

# Function to deploy frontend
deploy_frontend() {
    print_status "Deploying Streamlit frontend..."

    # Get service URLs
    N8N_WEBHOOK_URL="http://n8n:5678/webhook/flood-detection"
    BACKEND_MCP_URL="http://flood-detection-backend:8080"

    oc process -f "$TEMPLATES_DIR/frontend-template.yaml" \
        -p GIT_REPO_URL="$GIT_REPO_URL" \
        -p GIT_REF="$GIT_REF" \
        -p N8N_WEBHOOK_URL="$N8N_WEBHOOK_URL" \
        -p BACKEND_MCP_URL="$BACKEND_MCP_URL" \
        | oc apply -f -

    print_status "Starting frontend build..."
    oc start-build flood-detection-frontend --follow

    print_status "Waiting for frontend to be ready..."
    oc rollout status dc/flood-detection-frontend --timeout=300s

    print_success "Frontend deployed successfully"
}

# Function to display access information
show_access_info() {
    print_success "Deployment completed successfully!"
    echo
    print_status "Access URLs:"

    # Get route URLs
    FRONTEND_URL=$(oc get route flood-detection-frontend -o jsonpath='{.spec.host}' 2>/dev/null || echo "Not found")
    BACKEND_URL=$(oc get route flood-detection-backend -o jsonpath='{.spec.host}' 2>/dev/null || echo "Not found")
    N8N_URL=$(oc get route n8n -o jsonpath='{.spec.host}' 2>/dev/null || echo "Not found")
    MINIO_CONSOLE_URL=$(oc get route minio-console -o jsonpath='{.spec.host}' 2>/dev/null || echo "Not found")

    if [[ "$FRONTEND_URL" != "Not found" ]]; then
        echo -e "${GREEN}Frontend (Streamlit):${NC} https://$FRONTEND_URL"
    fi

    if [[ "$BACKEND_URL" != "Not found" ]]; then
        echo -e "${GREEN}Backend API:${NC} https://$BACKEND_URL"
    fi

    if [[ "$N8N_URL" != "Not found" ]]; then
        echo -e "${GREEN}n8n Workflows:${NC} https://$N8N_URL"
        echo -e "  ${YELLOW}Username:${NC} $N8N_BASIC_AUTH_USER"
        echo -e "  ${YELLOW}Password:${NC} $N8N_BASIC_AUTH_PASSWORD"
    fi

    if [[ "$MINIO_CONSOLE_URL" != "Not found" ]]; then
        echo -e "${GREEN}MinIO Console:${NC} https://$MINIO_CONSOLE_URL"
        echo -e "  ${YELLOW}Username:${NC} $MINIO_ACCESS_KEY"
        echo -e "  ${YELLOW}Password:${NC} $MINIO_SECRET_KEY"
    fi

    echo
    print_status "To monitor deployment status:"
    echo "  oc get pods -w"
    echo "  oc logs -f dc/flood-detection-backend"
    echo
    print_status "To clean up:"
    echo "  oc delete project $PROJECT_NAME"
}

# Main deployment function
main() {
    print_status "Starting Flood Detection System deployment to OpenShift..."

    check_prerequisites
    read_credentials
    setup_project

    print_status "Deploying components in order..."
    deploy_minio
    deploy_backend
    deploy_n8n
    deploy_frontend

    show_access_info
}

# Handle script arguments
case "${1:-}" in
    "minio")
        check_prerequisites
        read_credentials
        setup_project
        deploy_minio
        ;;
    "backend")
        check_prerequisites
        read_credentials
        setup_project
        deploy_backend
        ;;
    "n8n")
        check_prerequisites
        read_credentials
        setup_project
        deploy_n8n
        ;;
    "frontend")
        check_prerequisites
        read_credentials
        setup_project
        deploy_frontend
        ;;
    "clean")
        print_warning "This will delete the entire $PROJECT_NAME project"
        read -p "Are you sure? (y/N): " confirm
        if [[ $confirm == [yY] ]]; then
            oc delete project "$PROJECT_NAME"
            print_success "Project $PROJECT_NAME deleted"
        fi
        ;;
    "")
        main
        ;;
    *)
        echo "Usage: $0 [minio|backend|n8n|frontend|clean]"
        echo "  No arguments: Deploy full system"
        echo "  minio: Deploy only MinIO"
        echo "  backend: Deploy only backend"
        echo "  n8n: Deploy only n8n"
        echo "  frontend: Deploy only frontend"
        echo "  clean: Delete the project"
        exit 1
        ;;
esac