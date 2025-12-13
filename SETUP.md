# 🛠️ Setup Guide

> **Complete installation guide for the Sovereign Cognitive Engine**
>
> Don't worry if you've never used `nerdctl` or `containerd` before. This guide will walk you through every step.

---

## 📋 Table of Contents

1. [Quick Start (30 seconds)](#quick-start)
2. [What is nerdctl? (And why not Docker?)](#what-is-nerdctl)
3. [Installation by OS](#installation-by-os)
   - [Windows (WSL2)](#windows-wsl2)
   - [macOS](#macos)
   - [Linux (Ubuntu/Debian)](#linux)
4. [GPU Setup (NVIDIA only)](#gpu-setup)
5. [Verifying Your Installation](#verification)
6. [External Tools](#external-tools)
7. [Troubleshooting](#troubleshooting)

---

## Quick Start

Already have nerdctl + NVIDIA Container Toolkit? Just run:

```bash
git clone https://github.com/your-org/sovereign-cognitive-engine.git
cd sovereign-cognitive-engine
sh scripts/init.sh
```

Open **http://localhost:3000** when ready. ✅

---

## What is nerdctl?

### The Short Version

`nerdctl` is a Docker-compatible CLI that talks directly to `containerd` (the industry-standard container runtime). It's what Docker Desktop uses under the hood, but without the licensing costs or overhead.

### Why We Use It

| Feature | Docker Desktop | nerdctl + containerd |
|---------|---------------|---------------------|
| License | Free for small teams, paid for enterprise | 100% free, forever |
| Overhead | ~2GB RAM for desktop app | ~50MB for daemon |
| GPU Passthrough | Works, but can be finicky | Native NVIDIA integration |
| WSL2 Integration | Separate VM layer | Direct containerd access |

### The Commands Are (Almost) Identical

```bash
# Docker
docker run -it ubuntu bash
docker compose up -d

# nerdctl (same thing!)
nerdctl run -it ubuntu bash
nerdctl compose up -d
```

---

## Installation by OS

### Windows (WSL2)

> **Estimated time: 15 minutes**

#### Prerequisites
- Windows 10 (Build 19041+) or Windows 11
- NVIDIA GPU with driver 525.60.13+

#### Automated Install

```powershell
# Run PowerShell as Administrator
Set-ExecutionPolicy Bypass -Scope Process -Force
.\scripts\setup\install_wsl2.ps1
```

#### Manual Steps

<details>
<summary>Click to expand manual installation steps</summary>

**Step 1: Enable WSL2**

```powershell
# Enable WSL
wsl --install

# Set WSL2 as default
wsl --set-default-version 2

# Restart your computer
```

**Step 2: Install Ubuntu**

```powershell
wsl --install -d Ubuntu-22.04
```

**Step 3: Install NVIDIA Drivers for WSL2**

Download and install from: https://developer.nvidia.com/cuda/wsl/download

> ⚠️ **Important:** Install the *WSL2 specific* driver, NOT the regular Windows driver.

**Step 4: Install containerd + nerdctl (inside WSL)**

```bash
# Update packages
sudo apt update && sudo apt upgrade -y

# Install containerd
sudo apt install -y containerd

# Download nerdctl
NERDCTL_VERSION=1.7.0
curl -fsSL https://github.com/containerd/nerdctl/releases/download/v${NERDCTL_VERSION}/nerdctl-${NERDCTL_VERSION}-linux-amd64.tar.gz | sudo tar -xzf - -C /usr/local/bin

# Install CNI plugins
CNI_VERSION=1.3.0
sudo mkdir -p /opt/cni/bin
curl -fsSL https://github.com/containernetworking/plugins/releases/download/v${CNI_VERSION}/cni-plugins-linux-amd64-v${CNI_VERSION}.tgz | sudo tar -xzf - -C /opt/cni/bin

# Install NVIDIA Container Toolkit
distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
curl -s -L https://nvidia.github.io/libnvidia-container/$distribution/libnvidia-container.list | \
    sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | \
    sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list
sudo apt update
sudo apt install -y nvidia-container-toolkit

# Configure containerd for NVIDIA
sudo nvidia-ctk runtime configure --runtime=containerd
sudo systemctl restart containerd
```

</details>

---

### macOS

> **Estimated time: 20 minutes**
>
> ⚠️ **Note:** macOS has NO GPU support for NVIDIA. TTS/LLM will run on CPU (slow) or you'll need to use a remote GPU server.

#### Automated Install

```bash
chmod +x scripts/setup/install_mac.sh
./scripts/setup/install_mac.sh
```

#### Manual Steps

<details>
<summary>Click to expand manual installation steps</summary>

**Step 1: Install Lima**

```bash
# Install Homebrew if you don't have it
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Install Lima
brew install lima
```

**Step 2: Create a Lima Instance**

```bash
# Create instance with optimized settings
limactl create --name=sce --cpus=4 --memory=8 --mount-type=virtiofs template://default

# Start the instance
limactl start sce
```

**Step 3: Install nerdctl Inside Lima**

```bash
# Enter the Lima shell
limactl shell sce

# Install nerdctl (inside Lima)
NERDCTL_VERSION=1.7.0
curl -fsSL https://github.com/containerd/nerdctl/releases/download/v${NERDCTL_VERSION}/nerdctl-${NERDCTL_VERSION}-linux-amd64.tar.gz | sudo tar -xzf - -C /usr/local/bin

# Exit Lima shell
exit
```

**Step 4: Create Helper Alias**

Add to your `~/.zshrc` or `~/.bashrc`:

```bash
# Alias nerdctl to run inside Lima
alias nerdctl="limactl shell sce nerdctl"
alias nerdctl-compose="limactl shell sce nerdctl compose"
```

Reload your shell:

```bash
source ~/.zshrc
```

</details>

---

### Linux

> **Estimated time: 10 minutes**

#### Automated Install

```bash
chmod +x scripts/setup/install_linux.sh
sudo ./scripts/setup/install_linux.sh
```

#### Manual Steps

<details>
<summary>Click to expand manual installation steps</summary>

**Step 1: Install containerd**

```bash
# Add Docker's official GPG key
sudo apt-get update
sudo apt-get install ca-certificates curl gnupg
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg

# Add the repository
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# Install containerd
sudo apt-get update
sudo apt-get install -y containerd.io

# Start containerd
sudo systemctl enable --now containerd
```

**Step 2: Install nerdctl**

```bash
NERDCTL_VERSION=1.7.0
curl -fsSL https://github.com/containerd/nerdctl/releases/download/v${NERDCTL_VERSION}/nerdctl-${NERDCTL_VERSION}-linux-amd64.tar.gz | sudo tar -xzf - -C /usr/local/bin

# Install CNI plugins
CNI_VERSION=1.3.0
sudo mkdir -p /opt/cni/bin
curl -fsSL https://github.com/containernetworking/plugins/releases/download/v${CNI_VERSION}/cni-plugins-linux-amd64-v${CNI_VERSION}.tgz | sudo tar -xzf - -C /opt/cni/bin
```

**Step 3: Install NVIDIA Container Toolkit**

```bash
distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
curl -s -L https://nvidia.github.io/libnvidia-container/$distribution/libnvidia-container.list | \
    sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | \
    sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list

sudo apt-get update
sudo apt-get install -y nvidia-container-toolkit

# Configure for containerd
sudo nvidia-ctk runtime configure --runtime=containerd
sudo systemctl restart containerd
```

**Step 4 (Optional): Enable Rootless Mode**

For extra security and speed:

```bash
# Install rootless dependencies
sudo apt-get install -y uidmap

# Install rootlesskit with bypass4netns for faster networking
curl -fsSL https://github.com/rootless-containers/bypass4netns/releases/download/v0.4.1/bypass4netns-x86_64 -o ~/.local/bin/bypass4netns
chmod +x ~/.local/bin/bypass4netns

# Configure containerd for rootless
containerd-rootless-setuptool.sh install

# Add to your bashrc
echo 'export CONTAINERD_SNAPSHOTTER=native' >> ~/.bashrc
echo 'export BYPASS4NETNS=true' >> ~/.bashrc
```

</details>

---

## GPU Setup

### Verify NVIDIA Driver

```bash
# Should show your GPU(s)
nvidia-smi
```

Expected output:
```
+-----------------------------------------------------------------------------+
| NVIDIA-SMI 535.154.05   Driver Version: 535.154.05   CUDA Version: 12.2     |
|-------------------------------+----------------------+----------------------+
| GPU  Name        Persistence-M| Bus-Id        Disp.A | Volatile Uncorr. ECC |
| Fan  Temp  Perf  Pwr:Usage/Cap|         Memory-Usage | GPU-Util  Compute M. |
|===============================+======================+======================|
|   0  NVIDIA GeForce ...  Off  | 00000000:01:00.0 Off |                  N/A |
|  0%   45C    P8    15W / 350W |      0MiB / 24576MiB |      0%      Default |
+-------------------------------+----------------------+----------------------+
```

### Test GPU in Containers

```bash
# This should show GPU info inside the container
nerdctl run --rm --gpus all nvidia/cuda:12.0-base-ubuntu22.04 nvidia-smi
```

---

## Verification

Run our verification script:

```bash
./scripts/verify_install.sh
```

Or check manually:

```bash
# Check nerdctl
nerdctl --version
# Expected: nerdctl version 1.7.0

# Check containerd
sudo ctr version
# Expected: Client/Server version info

# Check GPU passthrough
nerdctl run --rm --gpus all nvidia/cuda:12.0-base-ubuntu22.04 nvidia-smi
# Expected: GPU info inside container

# Check compose
nerdctl compose version
# Expected: nerdctl compose version v1.7.0
```

---

## External Tools

These aren't required, but they make development easier.

### VS Code Remote Development

**Attach to the running backend container for debugging:**

1. Install the "Dev Containers" extension in VS Code
2. Open Command Palette (`Ctrl+Shift+P`)
3. Run: `Dev Containers: Attach to Running Container...`
4. Select `orchestrator` (the backend container)

You can now:
- Set breakpoints in Python code
- Use the integrated terminal inside the container
- Edit files with full IntelliSense

### Neo4j Browser (Graph Visualization)

**Manually explore your knowledge graph:**

1. Ensure containers are running: `nerdctl compose up -d`
2. Open http://localhost:7474 in your browser
3. Login with:
   - Username: `neo4j`
   - Password: (check your `.env` file, default: `sovereign2024`)

**Useful Cypher queries:**

```cypher
// See all entities
MATCH (n:Entity) RETURN n LIMIT 100

// See entity relationships
MATCH (a:Entity)-[r]->(b:Entity) RETURN a, r, b LIMIT 50

// Find specific entity
MATCH (n:Entity {name: "Einstein"}) RETURN n
```

### Milvus Attu (Vector DB GUI)

**Visualize your embeddings:**

1. Install Attu: https://github.com/zilliztech/attu
2. Connect to `localhost:19530`
3. Browse collections and vectors

### FFmpeg (Audio Processing)

FFmpeg runs inside containers, but if you want it locally:

```bash
# Ubuntu/Debian
sudo apt install ffmpeg

# macOS
brew install ffmpeg

# Windows (WSL)
sudo apt install ffmpeg
```

---

## Troubleshooting

### "nerdctl: command not found"

```bash
# Add to PATH
export PATH=$PATH:/usr/local/bin

# Make permanent
echo 'export PATH=$PATH:/usr/local/bin' >> ~/.bashrc
source ~/.bashrc
```

### "permission denied" errors

```bash
# Make sure containerd is running
sudo systemctl status containerd

# If not running
sudo systemctl start containerd
sudo systemctl enable containerd
```

### WSL2: "GPU not detected"

1. Make sure you installed the WSL2-specific NVIDIA driver
2. Restart WSL: `wsl --shutdown` then reopen
3. Verify in Windows: Run `nvidia-smi` in PowerShell first

### macOS: "Lima is slow"

Ensure you're using `virtiofs` mount type:

```bash
# Check current config
limactl list

# Recreate with virtiofs if needed
limactl delete sce
limactl create --name=sce --mount-type=virtiofs template://default
```

### "CUDA out of memory"

See the [VRAM Troubleshooting table in README.md](README.md#-vram-troubleshooting).

---

## Next Steps

1. ✅ Installation complete
2. 👉 Run `sh scripts/init.sh` to start the stack
3. 👉 Open http://localhost:3000
4. 👉 Upload your first PDF!

---

<div align="center">

**Need help?** [Open an issue](https://github.com/your-org/sovereign-cognitive-engine/issues)

</div>
