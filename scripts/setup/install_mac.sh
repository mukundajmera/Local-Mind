#!/bin/bash
# ==============================================================================
# Sovereign Cognitive Engine - macOS Installation Script
# ==============================================================================
# This script sets up Lima with nerdctl on macOS.
#
# Note: macOS does NOT support NVIDIA GPU passthrough.
# AI models will run on CPU (slow) unless you use a remote GPU.
#
# Usage:
#   chmod +x scripts/setup/install_mac.sh
#   ./scripts/setup/install_mac.sh
#
# ==============================================================================

set -e

# Configuration
LIMA_INSTANCE_NAME="sce"
LIMA_CPUS=4
LIMA_MEMORY=8   # GB
NERDCTL_VERSION="1.7.0"

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

# Check if running on macOS
if [[ "$OSTYPE" != "darwin"* ]]; then
    print_error "This script is for macOS only."
    exit 1
fi

print_success "Running on macOS: $(sw_vers -productVersion)"

# Check architecture
ARCH=$(uname -m)
print_info "Architecture: $ARCH"

if [[ "$ARCH" != "arm64" && "$ARCH" != "x86_64" ]]; then
    print_error "Unsupported architecture: $ARCH"
    exit 1
fi

# ==============================================================================
# Install Homebrew
# ==============================================================================

print_header "Checking Homebrew"

if ! command -v brew &> /dev/null; then
    print_info "Installing Homebrew..."
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    
    # Add Homebrew to PATH for Apple Silicon
    if [[ "$ARCH" == "arm64" ]]; then
        echo 'eval "$(/opt/homebrew/bin/brew shellenv)"' >> ~/.zprofile
        eval "$(/opt/homebrew/bin/brew shellenv)"
    fi
else
    print_success "Homebrew already installed"
fi

# Update Homebrew
print_info "Updating Homebrew..."
brew update

# ==============================================================================
# Install Lima
# ==============================================================================

print_header "Installing Lima"

if ! command -v limactl &> /dev/null; then
    print_info "Installing Lima..."
    brew install lima
else
    print_success "Lima already installed: $(limactl --version)"
fi

# Also install useful tools
print_info "Installing additional tools..."
brew install jq qemu

# ==============================================================================
# Create Lima Instance
# ==============================================================================

print_header "Creating Lima Instance"

# Check if instance already exists
if limactl list 2>/dev/null | grep -q "^$LIMA_INSTANCE_NAME "; then
    print_warning "Lima instance '$LIMA_INSTANCE_NAME' already exists."
    read -p "Delete and recreate? (y/n): " response
    if [[ "$response" == "y" ]]; then
        limactl stop $LIMA_INSTANCE_NAME 2>/dev/null || true
        limactl delete $LIMA_INSTANCE_NAME
    else
        print_info "Using existing instance."
    fi
fi

# Create Lima configuration file
LIMA_CONFIG=$(mktemp)
cat > "$LIMA_CONFIG" << EOF
# Lima configuration for Sovereign Cognitive Engine
# Optimized for development with virtiofs mounts

images:
  - location: "https://cloud-images.ubuntu.com/releases/22.04/release/ubuntu-22.04-server-cloudimg-amd64.img"
    arch: "x86_64"
  - location: "https://cloud-images.ubuntu.com/releases/22.04/release/ubuntu-22.04-server-cloudimg-arm64.img"
    arch: "aarch64"

cpus: $LIMA_CPUS
memory: "${LIMA_MEMORY}GiB"
disk: "50GiB"

# Use virtiofs for much better I/O performance (macOS 13+)
mountType: "virtiofs"

mounts:
  - location: "~"
    writable: true
  - location: "/tmp/lima"
    writable: true

# Forward ports from the VM
portForwards:
  - guestPort: 3000
    hostPort: 3000
    protocol: tcp
  - guestPort: 8000
    hostPort: 8000
    protocol: tcp
  - guestPort: 7474
    hostPort: 7474
    protocol: tcp
  - guestPort: 7687
    hostPort: 7687
    protocol: tcp

# Provision script to install nerdctl
provision:
  - mode: system
    script: |
      #!/bin/bash
      set -eux -o pipefail
      
      # Install dependencies
      apt-get update
      apt-get install -y curl ca-certificates
      
      # Install containerd
      apt-get install -y containerd
      systemctl enable --now containerd
      
      # Install nerdctl
      NERDCTL_VERSION="${NERDCTL_VERSION}"
      curl -fsSL https://github.com/containerd/nerdctl/releases/download/v\${NERDCTL_VERSION}/nerdctl-\${NERDCTL_VERSION}-linux-amd64.tar.gz | tar -xzf - -C /usr/local/bin
      
      # Install CNI plugins
      CNI_VERSION="1.3.0"
      mkdir -p /opt/cni/bin
      curl -fsSL https://github.com/containernetworking/plugins/releases/download/v\${CNI_VERSION}/cni-plugins-linux-amd64-v\${CNI_VERSION}.tgz | tar -xzf - -C /opt/cni/bin
      
      # Install buildkit
      BUILDKIT_VERSION="0.12.4"
      mkdir -p /usr/local/lib/buildkit
      curl -fsSL https://github.com/moby/buildkit/releases/download/v\${BUILDKIT_VERSION}/buildkit-v\${BUILDKIT_VERSION}.linux-amd64.tar.gz | tar -xzf - -C /usr/local/lib/buildkit
      
      echo "nerdctl installation complete!"
EOF

# Create the instance if it doesn't exist
if ! limactl list 2>/dev/null | grep -q "^$LIMA_INSTANCE_NAME "; then
    print_info "Creating Lima instance '$LIMA_INSTANCE_NAME'..."
    print_info "This may take several minutes..."
    
    limactl create --name="$LIMA_INSTANCE_NAME" "$LIMA_CONFIG"
fi

rm -f "$LIMA_CONFIG"

# Start the instance
print_info "Starting Lima instance..."
limactl start "$LIMA_INSTANCE_NAME"

print_success "Lima instance created and running"

# ==============================================================================
# Create Shell Aliases
# ==============================================================================

print_header "Setting Up Shell Aliases"

# Detect shell
SHELL_RC=""
if [[ -n "${ZSH_VERSION:-}" ]] || [[ "$SHELL" == *"zsh"* ]]; then
    SHELL_RC="$HOME/.zshrc"
elif [[ -n "${BASH_VERSION:-}" ]] || [[ "$SHELL" == *"bash"* ]]; then
    SHELL_RC="$HOME/.bashrc"
fi

if [[ -n "$SHELL_RC" ]]; then
    # Check if aliases already exist
    if ! grep -q "alias nerdctl=" "$SHELL_RC" 2>/dev/null; then
        print_info "Adding nerdctl aliases to $SHELL_RC"
        
        cat >> "$SHELL_RC" << 'EOF'

# Sovereign Cognitive Engine - Lima/nerdctl aliases
alias nerdctl="limactl shell sce nerdctl"
alias nerdctl-compose="limactl shell sce nerdctl compose"
alias lima-shell="limactl shell sce"

# Helper function to run commands in Lima
lima() {
    limactl shell sce "$@"
}
EOF
        print_success "Aliases added. Run 'source $SHELL_RC' to activate."
    else
        print_success "Aliases already configured"
    fi
fi

# ==============================================================================
# Verification
# ==============================================================================

print_header "Verification"

print_info "Checking nerdctl inside Lima..."
limactl shell "$LIMA_INSTANCE_NAME" nerdctl --version

print_info "Checking containerd..."
limactl shell "$LIMA_INSTANCE_NAME" sudo ctr version

print_info "Testing container run..."
limactl shell "$LIMA_INSTANCE_NAME" nerdctl run --rm hello-world

# ==============================================================================
# Complete
# ==============================================================================

print_header "Setup Complete!"

cat << EOF

${GREEN}Your macOS development environment is ready!${NC}

${YELLOW}Important Notes for macOS:${NC}
  • No NVIDIA GPU support on macOS
  • AI models will run on CPU (slower)
  • Consider using a remote GPU server for production

${BLUE}Usage:${NC}

  # Enter Lima shell
  limactl shell sce

  # Or use the aliases (after reloading shell)
  source ~/.zshrc
  nerdctl run hello-world

  # Start the stack (inside Lima shell)
  lima-shell
  cd ~/path/to/sovereign-cognitive-engine
  sh scripts/init.sh

${BLUE}Useful Commands:${NC}

  limactl list              # List instances
  limactl stop sce          # Stop the VM
  limactl start sce         # Start the VM
  limactl shell sce         # Enter shell

For more information, see SETUP.md

EOF
