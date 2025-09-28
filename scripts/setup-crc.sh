#!/bin/bash

# OpenShift Local (CRC) Setup Script
# This script automates the installation and setup of CodeReady Containers

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

# Function to detect OS
detect_os() {
    case "$(uname -s)" in
        Darwin*)
            OS="macos"
            ARCH="amd64"
            if [[ "$(uname -m)" == "arm64" ]]; then
                ARCH="arm64"
            fi
            ;;
        Linux*)
            OS="linux"
            ARCH="amd64"
            ;;
        MINGW*|CYGWIN*|MSYS*)
            OS="windows"
            ARCH="amd64"
            ;;
        *)
            print_error "Unsupported operating system: $(uname -s)"
            exit 1
            ;;
    esac

    print_status "Detected OS: $OS-$ARCH"
}

# Function to check system requirements
check_requirements() {
    print_status "Checking system requirements..."

    # Check available memory
    case "$OS" in
        macos)
            TOTAL_MEM_KB=$(sysctl -n hw.memsize)
            TOTAL_MEM_GB=$((TOTAL_MEM_KB / 1024 / 1024 / 1024))
            ;;
        linux)
            TOTAL_MEM_KB=$(grep MemTotal /proc/meminfo | awk '{print $2}')
            TOTAL_MEM_GB=$((TOTAL_MEM_KB / 1024 / 1024))
            ;;
        windows)
            # Assume sufficient memory on Windows
            TOTAL_MEM_GB=16
            ;;
    esac

    if [[ $TOTAL_MEM_GB -lt 9 ]]; then
        print_warning "System has ${TOTAL_MEM_GB}GB RAM. CRC requires minimum 9GB."
        print_warning "You may experience performance issues."
    else
        print_success "Memory check passed: ${TOTAL_MEM_GB}GB available"
    fi

    # Check available disk space
    case "$OS" in
        macos|linux)
            AVAILABLE_GB=$(df -BG . | awk 'NR==2 {print $4}' | sed 's/G//')
            ;;
        windows)
            # Assume sufficient disk space on Windows
            AVAILABLE_GB=100
            ;;
    esac

    if [[ $AVAILABLE_GB -lt 35 ]]; then
        print_error "Insufficient disk space. CRC requires minimum 35GB, available: ${AVAILABLE_GB}GB"
        exit 1
    else
        print_success "Disk space check passed: ${AVAILABLE_GB}GB available"
    fi
}

# Function to install prerequisites
install_prerequisites() {
    print_status "Installing prerequisites for $OS..."

    case "$OS" in
        macos)
            # macOS uses built-in hypervisor, no additional packages needed
            print_status "macOS uses built-in hypervisor - no additional packages required"
            ;;
        linux)
            # Install libvirt and NetworkManager
            if command -v yum >/dev/null 2>&1; then
                print_status "Installing prerequisites with yum..."
                sudo yum -y install qemu-kvm libvirt virt-install bridge-utils NetworkManager
            elif command -v dnf >/dev/null 2>&1; then
                print_status "Installing prerequisites with dnf..."
                sudo dnf install -y NetworkManager qemu-kvm libvirt virt-install
            elif command -v apt >/dev/null 2>&1; then
                print_status "Installing prerequisites with apt..."
                sudo apt update
                sudo apt install -y qemu-kvm libvirt-daemon libvirt-daemon-system network-manager
            else
                print_error "Could not detect package manager. Please install libvirt and NetworkManager manually."
                exit 1
            fi

            # Start and enable libvirt
            sudo systemctl start libvirtd
            sudo systemctl enable libvirtd

            # Add user to libvirt group
            sudo usermod -aG libvirt $USER
            print_warning "You may need to log out and back in for group changes to take effect"
            ;;
        windows)
            print_status "Please ensure Hyper-V is enabled on Windows"
            print_status "Run 'Enable-WindowsOptionalFeature -Online -FeatureName Microsoft-Hyper-V -All' in PowerShell as Administrator"
            ;;
    esac

    print_success "Prerequisites installation completed"
}

# Function to download and install CRC
install_crc() {
    print_status "Downloading and installing CRC..."

    # Get latest version
    LATEST_VERSION=$(curl -s https://api.github.com/repos/crc-org/crc/releases/latest | grep '"tag_name"' | sed -E 's/.*"([^"]+)".*/\1/' | sed 's/v//')
    print_status "Latest CRC version: $LATEST_VERSION"

    # Construct download URL
    case "$OS" in
        macos)
            if [[ "$ARCH" == "arm64" ]]; then
                DOWNLOAD_URL="https://mirror.openshift.com/pub/openshift-v4/clients/crc/latest/crc-macos-amd64.tar.xz"
                print_warning "Using x64 version on Apple Silicon (will run under Rosetta)"
            else
                DOWNLOAD_URL="https://mirror.openshift.com/pub/openshift-v4/clients/crc/latest/crc-macos-amd64.tar.xz"
            fi
            ARCHIVE_NAME="crc-macos-amd64.tar.xz"
            ;;
        linux)
            DOWNLOAD_URL="https://mirror.openshift.com/pub/openshift-v4/clients/crc/latest/crc-linux-amd64.tar.xz"
            ARCHIVE_NAME="crc-linux-amd64.tar.xz"
            ;;
        windows)
            print_status "Please download CRC for Windows from:"
            print_status "https://mirror.openshift.com/pub/openshift-v4/clients/crc/latest/crc-windows-amd64.zip"
            return 0
            ;;
    esac

    # Download CRC
    print_status "Downloading from: $DOWNLOAD_URL"
    curl -LO "$DOWNLOAD_URL"

    # Extract and install
    print_status "Extracting $ARCHIVE_NAME..."
    tar -xf "$ARCHIVE_NAME"

    # Find the crc binary and install it
    CRC_BINARY=$(find . -name "crc" -type f | head -1)
    if [[ -z "$CRC_BINARY" ]]; then
        print_error "Could not find crc binary in extracted files"
        exit 1
    fi

    print_status "Installing CRC to /usr/local/bin/..."
    sudo mv "$CRC_BINARY" /usr/local/bin/crc
    sudo chmod +x /usr/local/bin/crc

    # Clean up
    rm -rf crc-* "$ARCHIVE_NAME"

    print_success "CRC installed successfully"
    crc version
}

# Function to configure CRC
configure_crc() {
    print_status "Configuring CRC..."

    # Setup CRC
    print_status "Running crc setup..."
    crc setup

    # Configure resources based on system capabilities
    if [[ $TOTAL_MEM_GB -ge 16 ]]; then
        print_status "Configuring CRC with 12GB memory..."
        crc config set memory 12288
    else
        print_status "Configuring CRC with 9GB memory..."
        crc config set memory 9216
    fi

    # Set CPU count
    case "$OS" in
        macos)
            CPU_COUNT=$(sysctl -n hw.ncpu)
            ;;
        linux)
            CPU_COUNT=$(nproc)
            ;;
        windows)
            CPU_COUNT=4
            ;;
    esac

    if [[ $CPU_COUNT -ge 6 ]]; then
        print_status "Configuring CRC with 4 CPUs..."
        crc config set cpus 4
    else
        print_status "Configuring CRC with 2 CPUs..."
        crc config set cpus 2
    fi

    # Set disk size
    print_status "Configuring CRC with 60GB disk..."
    crc config set disk-size 60

    print_success "CRC configuration completed"
    crc config view
}

# Function to check for pull secret
check_pull_secret() {
    print_status "Checking for pull secret..."

    PULL_SECRET_PATHS=(
        "$HOME/Downloads/pull-secret.txt"
        "$HOME/pull-secret.txt"
        "./pull-secret.txt"
    )

    for path in "${PULL_SECRET_PATHS[@]}"; do
        if [[ -f "$path" ]]; then
            PULL_SECRET_FILE="$path"
            print_success "Found pull secret at: $PULL_SECRET_FILE"
            return 0
        fi
    done

    print_warning "Pull secret not found in common locations"
    print_status "Please download your pull secret from:"
    print_status "https://developers.redhat.com/products/openshift-local/overview"
    print_status "Save it as ~/Downloads/pull-secret.txt"

    read -p "Press Enter after downloading the pull secret..."
    check_pull_secret
}

# Function to start CRC
start_crc() {
    print_status "Starting CRC cluster..."

    if ! crc start --pull-secret-file "$PULL_SECRET_FILE"; then
        print_error "Failed to start CRC cluster"
        print_status "You can try again with: crc start --pull-secret-file $PULL_SECRET_FILE"
        exit 1
    fi

    print_success "CRC cluster started successfully"

    # Setup oc CLI
    print_status "Setting up oc CLI access..."
    eval $(crc oc-env)

    # Get cluster info
    print_status "Cluster information:"
    crc console --credentials

    print_success "CRC setup completed!"
    print_status "You can now access:"
    echo "  - OpenShift Console: $(crc console --url)"
    echo "  - CLI access: eval \$(crc oc-env)"
    echo "  - Deploy flood detection: ./openshift/scripts/deploy-openshift.sh"
}

# Main function
main() {
    print_status "Starting OpenShift Local (CRC) setup..."

    detect_os
    check_requirements

    # Check if CRC is already installed
    if command -v crc >/dev/null 2>&1; then
        print_warning "CRC is already installed"
        print_status "Current version: $(crc version)"
        read -p "Do you want to reconfigure CRC? (y/N): " reconfigure
        if [[ $reconfigure == [yY] ]]; then
            configure_crc
        fi
    else
        install_prerequisites
        install_crc
        configure_crc
    fi

    check_pull_secret
    start_crc
}

# Handle script arguments
case "${1:-}" in
    "install")
        detect_os
        check_requirements
        install_prerequisites
        install_crc
        configure_crc
        ;;
    "start")
        check_pull_secret
        start_crc
        ;;
    "stop")
        print_status "Stopping CRC cluster..."
        crc stop
        print_success "CRC cluster stopped"
        ;;
    "delete")
        print_warning "This will delete the CRC cluster and all data"
        read -p "Are you sure? (y/N): " confirm
        if [[ $confirm == [yY] ]]; then
            crc delete
            print_success "CRC cluster deleted"
        fi
        ;;
    "status")
        crc status
        ;;
    "")
        main
        ;;
    *)
        echo "Usage: $0 [install|start|stop|delete|status]"
        echo "  No arguments: Complete setup"
        echo "  install: Install and configure CRC"
        echo "  start: Start CRC cluster"
        echo "  stop: Stop CRC cluster"
        echo "  delete: Delete CRC cluster"
        echo "  status: Show CRC status"
        exit 1
        ;;
esac