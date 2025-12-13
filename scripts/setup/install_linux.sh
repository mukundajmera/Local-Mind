#!/bin/bash
# ==============================================================================
# Sovereign Cognitive Engine - Linux (Ubuntu/Debian) Installation Script
# ==============================================================================
# This script installs containerd, nerdctl, and NVIDIA Container Toolkit.
#
# Tested on: Ubuntu 22.04, Debian 12
#
# Usage:
#   chmod +x scripts/setup/install_linux.sh
#   sudo ./scripts/setup/install_linux.sh
#
# ==============================================================================

set -e

# Configuration
NERDCTL_VERSION="1.7.0"
CNI_VERSION="1.3.0"
BUILDKIT_VERSION="0.12.4"
ENABLE_ROOTLESS=false  # Set to true for rootless mode

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

print_header() {
    echo ""
    echo -e "${BLUE}==============================================================${NC}"
    echo -e "${BLUE}  $1${NC}"
    echo -e "${BLUE}==============================================================${NC}"
    echo ""
}

print_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
print_success() { echo -e "${GREEN}[OK]${NC} $1"; }
print_warning() { echo -e "${YELLOW}[WARN]${NC} $1"; }
print_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# ==============================================================================
# Check Prerequisites
# ==============================================================================

print_header "Checking Prerequisites"

# Check if running as root
if [[ $EUID -ne 0 ]]; then
    print_error "This script must be run as root (sudo)"
    exit 1
fi

# Check distribution
if [ -f /etc/os-release ]; then
    . /etc/os-release
    DISTRO=$ID
    VERSION=$VERSION_ID
else
    print_error "Cannot determine Linux distribution"
    exit 1
fi

print_info "Detected: $DISTRO $VERSION"

# Check supported distributions
case $DISTRO in
    ubuntu|debian|linuxmint|pop)
        print_success "Supported distribution"
        ;;
    *)
        print_warning "This script is tested on Ubuntu/Debian. Proceeding anyway..."
        ;;
esac

# Check architecture
ARCH=$(uname -m)
case $ARCH in
    x86_64)
        ARCH_SUFFIX="amd64"
        ;;
    aarch64)
        ARCH_SUFFIX="arm64"
        ;;
    *)
        print_error "Unsupported architecture: $ARCH"
        exit 1
        ;;
esac

print_info "Architecture: $ARCH ($ARCH_SUFFIX)"

# ==============================================================================
# Install Dependencies
# ==============================================================================

print_header "Installing Dependencies"

apt-get update
apt-get install -y \
    curl \
    ca-certificates \
    gnupg \
    lsb-release \
    iptables \
    uidmap \
    fuse-overlayfs

print_success "Dependencies installed"

# ==============================================================================
# Install containerd
# ==============================================================================

print_header "Installing containerd"

# Remove old versions
apt-get remove -y containerd containerd.io runc 2>/dev/null || true

# Add Docker's official GPG key (containerd.io is from Docker repo)
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/$DISTRO/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg 2>/dev/null || true
chmod a+r /etc/apt/keyrings/docker.gpg

# Add the repository
echo \
  "deb [arch=$ARCH_SUFFIX signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/$DISTRO \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
  tee /etc/apt/sources.list.d/docker.list > /dev/null

apt-get update
apt-get install -y containerd.io

# Configure containerd
mkdir -p /etc/containerd
containerd config default > /etc/containerd/config.toml

# Enable systemd cgroup driver
sed -i 's/SystemdCgroup = false/SystemdCgroup = true/' /etc/containerd/config.toml

# Start containerd
systemctl enable containerd
systemctl restart containerd

print_success "containerd installed and running"

# ==============================================================================
# Install nerdctl
# ==============================================================================

print_header "Installing nerdctl"

# Download nerdctl binary
curl -fsSL "https://github.com/containerd/nerdctl/releases/download/v${NERDCTL_VERSION}/nerdctl-${NERDCTL_VERSION}-linux-${ARCH_SUFFIX}.tar.gz" | \
    tar -xzf - -C /usr/local/bin

chmod +x /usr/local/bin/nerdctl

print_success "nerdctl ${NERDCTL_VERSION} installed"

# ==============================================================================
# Install CNI Plugins
# ==============================================================================

print_header "Installing CNI Plugins"

mkdir -p /opt/cni/bin

curl -fsSL "https://github.com/containernetworking/plugins/releases/download/v${CNI_VERSION}/cni-plugins-linux-${ARCH_SUFFIX}-v${CNI_VERSION}.tgz" | \
    tar -xzf - -C /opt/cni/bin

print_success "CNI plugins installed"

# ==============================================================================
# Install BuildKit
# ==============================================================================

print_header "Installing BuildKit"

mkdir -p /usr/local/lib/buildkit

curl -fsSL "https://github.com/moby/buildkit/releases/download/v${BUILDKIT_VERSION}/buildkit-v${BUILDKIT_VERSION}.linux-${ARCH_SUFFIX}.tar.gz" | \
    tar -xzf - -C /usr/local/lib/buildkit

# Add buildkit to PATH
ln -sf /usr/local/lib/buildkit/bin/buildkitd /usr/local/bin/buildkitd
ln -sf /usr/local/lib/buildkit/bin/buildctl /usr/local/bin/buildctl

print_success "BuildKit installed"

# ==============================================================================
# Install NVIDIA Container Toolkit (if GPU present)
# ==============================================================================

print_header "Checking for NVIDIA GPU"

if command -v nvidia-smi &> /dev/null; then
    print_success "NVIDIA GPU detected"
    nvidia-smi --query-gpu=name --format=csv,noheader | head -1
    
    print_info "Installing NVIDIA Container Toolkit..."
    
    # Add NVIDIA repository
    curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | \
        gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg 2>/dev/null || true
    
    distribution=${DISTRO}${VERSION}
    curl -s -L "https://nvidia.github.io/libnvidia-container/$distribution/libnvidia-container.list" | \
        sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | \
        tee /etc/apt/sources.list.d/nvidia-container-toolkit.list > /dev/null
    
    apt-get update
    apt-get install -y nvidia-container-toolkit
    
    # Configure containerd for NVIDIA
    nvidia-ctk runtime configure --runtime=containerd
    systemctl restart containerd
    
    print_success "NVIDIA Container Toolkit installed"
else
    print_warning "No NVIDIA GPU detected. Skipping NVIDIA toolkit."
fi

# ==============================================================================
# Install bypass4netns (Rootless Networking Boost)
# ==============================================================================

print_header "Installing bypass4netns"

BYPASS4NETNS_VERSION="0.4.1"
BYPASS4NETNS_URL="https://github.com/rootless-containers/bypass4netns/releases/download/v${BYPASS4NETNS_VERSION}/bypass4netns-x86_64"

if [[ "$ARCH" == "x86_64" ]]; then
    curl -fsSL "$BYPASS4NETNS_URL" -o /usr/local/bin/bypass4netns
    chmod +x /usr/local/bin/bypass4netns
    print_success "bypass4netns installed (enables faster rootless networking)"
else
    print_warning "bypass4netns only available for x86_64, skipping"
fi

# ==============================================================================
# Configure Rootless Mode (Optional)
# ==============================================================================

if [ "$ENABLE_ROOTLESS" = true ]; then
    print_header "Configuring Rootless Mode"
    
    # Get the actual user (not root)
    REAL_USER=${SUDO_USER:-$USER}
    REAL_HOME=$(getent passwd "$REAL_USER" | cut -d: -f6)
    
    if [ -n "$REAL_USER" ] && [ "$REAL_USER" != "root" ]; then
        print_info "Setting up rootless mode for user: $REAL_USER"
        
        # Install rootless helper
        apt-get install -y rootlesskit slirp4netns
        
        # Allow user to use rootless containers
        echo "$REAL_USER:100000:65536" >> /etc/subuid
        echo "$REAL_USER:100000:65536" >> /etc/subgid
        
        # Create user systemd service
        sudo -u "$REAL_USER" mkdir -p "$REAL_HOME/.config/systemd/user"
        
        cat > "$REAL_HOME/.config/systemd/user/containerd.service" << 'EOF'
[Unit]
Description=containerd (rootless)

[Service]
ExecStart=/usr/local/bin/containerd-rootless-setuptool.sh -- containerd
Restart=always

[Install]
WantedBy=default.target
EOF
        
        chown "$REAL_USER:$REAL_USER" "$REAL_HOME/.config/systemd/user/containerd.service"
        
        print_success "Rootless mode configured for $REAL_USER"
        print_info "User should run: systemctl --user enable --now containerd"
        
        # Add bypass4netns environment variable
        echo 'export BYPASS4NETNS=true' >> "$REAL_HOME/.bashrc"
    else
        print_warning "Cannot configure rootless mode without a real user"
    fi
else
    print_info "Rootless mode not enabled. Running in system mode."
fi

# ==============================================================================
# Create nerdctl Completion
# ==============================================================================

print_header "Setting Up Shell Completion"

# Bash completion
nerdctl completion bash > /etc/bash_completion.d/nerdctl

# Zsh completion
if [ -d /usr/share/zsh/vendor-completions ]; then
    nerdctl completion zsh > /usr/share/zsh/vendor-completions/_nerdctl
fi

print_success "Shell completion configured"

# ==============================================================================
# Verification
# ==============================================================================

print_header "Verification"

print_info "Checking nerdctl..."
nerdctl --version

print_info "Checking containerd..."
ctr version

print_info "Testing container run..."
nerdctl run --rm hello-world

# Test GPU if available
if command -v nvidia-smi &> /dev/null; then
    print_info "Testing GPU passthrough..."
    if nerdctl run --rm --gpus all nvidia/cuda:12.0-base-ubuntu22.04 nvidia-smi; then
        print_success "GPU passthrough working!"
    else
        print_warning "GPU passthrough test failed"
    fi
fi

# ==============================================================================
# Complete
# ==============================================================================

print_header "Setup Complete!"

cat << EOF

${GREEN}Your Linux development environment is ready!${NC}

${BLUE}Installed Components:${NC}
  • containerd ${VERSION:-latest}
  • nerdctl ${NERDCTL_VERSION}
  • CNI plugins ${CNI_VERSION}
  • BuildKit ${BUILDKIT_VERSION}
EOF

if command -v nvidia-smi &> /dev/null; then
    echo "  • NVIDIA Container Toolkit"
fi

cat << EOF

${BLUE}Usage:${NC}

  # Run a container
  nerdctl run -it ubuntu bash
  
  # Run with GPU
  nerdctl run --gpus all nvidia/cuda:12.0-base-ubuntu22.04 nvidia-smi
  
  # Use compose
  nerdctl compose up -d

${BLUE}Start Sovereign Cognitive Engine:${NC}

  cd /path/to/sovereign-cognitive-engine
  sh scripts/init.sh

For more information, see SETUP.md

EOF

if [ "$ENABLE_ROOTLESS" = true ]; then
    cat << EOF
${YELLOW}Rootless Mode:${NC}

  As your regular user, run:
  systemctl --user enable --now containerd
  
  Then use nerdctl without sudo.

EOF
fi
