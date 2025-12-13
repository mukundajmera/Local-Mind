# ==============================================================================
# Local Mind - Windows WSL2 Installation Script
# ==============================================================================
# This script sets up the complete development environment on Windows.
#
# Run as Administrator:
#   Set-ExecutionPolicy Bypass -Scope Process -Force
#   .\scripts\setup\install_wsl2.ps1
#
# ==============================================================================

#Requires -RunAsAdministrator

$ErrorActionPreference = "Stop"

# Configuration
$NERDCTL_VERSION = "1.7.0"
$WSL_DISTRO = "Ubuntu-22.04"

# Colors for output
function Write-Info { param($Message) Write-Host "[INFO] " -ForegroundColor Blue -NoNewline; Write-Host $Message }
function Write-Success { param($Message) Write-Host "[OK] " -ForegroundColor Green -NoNewline; Write-Host $Message }
function Write-Warn { param($Message) Write-Host "[WARN] " -ForegroundColor Yellow -NoNewline; Write-Host $Message }
function Write-Err { param($Message) Write-Host "[ERROR] " -ForegroundColor Red -NoNewline; Write-Host $Message }

function Write-Header {
    param($Title)
    Write-Host ""
    Write-Host ("=" * 60) -ForegroundColor Cyan
    Write-Host "  $Title" -ForegroundColor Cyan
    Write-Host ("=" * 60) -ForegroundColor Cyan
    Write-Host ""
}

# ==============================================================================
# Step 1: Check Windows Version
# ==============================================================================

Write-Header "Checking Windows Version"

$buildNumber = (Get-ItemProperty "HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion").CurrentBuildNumber

Write-Info "Windows Build: $buildNumber"

if ([int]$buildNumber -lt 19041) {
    Write-Err "Windows Build 19041 or higher required for WSL2."
    Write-Err "Please update Windows and try again."
    exit 1
}

Write-Success "Windows version compatible"

# ==============================================================================
# Step 2: Enable WSL Features
# ==============================================================================

Write-Header "Enabling WSL2 Features"

$restartRequired = $false

# Check if WSL is already enabled
$wslEnabled = (Get-WindowsOptionalFeature -Online -FeatureName Microsoft-Windows-Subsystem-Linux).State

if ($wslEnabled -ne "Enabled") {
    Write-Info "Enabling Windows Subsystem for Linux..."
    Enable-WindowsOptionalFeature -Online -FeatureName Microsoft-Windows-Subsystem-Linux -NoRestart | Out-Null
    $restartRequired = $true
}
else {
    Write-Success "WSL already enabled"
}

# Check Virtual Machine Platform
$vmEnabled = (Get-WindowsOptionalFeature -Online -FeatureName VirtualMachinePlatform).State

if ($vmEnabled -ne "Enabled") {
    Write-Info "Enabling Virtual Machine Platform..."
    Enable-WindowsOptionalFeature -Online -FeatureName VirtualMachinePlatform -NoRestart | Out-Null
    $restartRequired = $true
}
else {
    Write-Success "Virtual Machine Platform already enabled"
}

if ($restartRequired) {
    Write-Warn "A restart is required to complete WSL installation."
    Write-Warn "After restarting, run this script again."
    
    $response = Read-Host "Restart now? (y/n)"
    if ($response -eq "y") {
        Restart-Computer
    }
    exit 0
}

# ==============================================================================
# Step 3: Set WSL2 as Default
# ==============================================================================

Write-Header "Configuring WSL2"

Write-Info "Setting WSL2 as default version..."
wsl --set-default-version 2 2>$null | Out-Null

Write-Success "WSL2 set as default"

# ==============================================================================
# Step 4: Install Ubuntu
# ==============================================================================

Write-Header "Installing Ubuntu for WSL2"

# Check if Ubuntu is already installed
$wslList = wsl --list --quiet 2>$null
$ubuntuInstalled = $wslList -match "Ubuntu"

if (-not $ubuntuInstalled) {
    Write-Info "Installing $WSL_DISTRO..."
    Write-Info "This may take a few minutes..."
    wsl --install -d $WSL_DISTRO --no-launch
    
    Write-Host ""
    Write-Host "Please complete Ubuntu setup:" -ForegroundColor Yellow
    Write-Host "  1. A new window will open"
    Write-Host "  2. Create a username (lowercase, no spaces)"
    Write-Host "  3. Create a password"
    Write-Host "  4. Close the Ubuntu window when done"
    Write-Host ""
    
    Read-Host "Press Enter to continue..."
    Start-Process -FilePath "wsl" -ArgumentList "-d", $WSL_DISTRO -Wait
}
else {
    Write-Success "Ubuntu already installed"
}

# ==============================================================================
# Step 5: NVIDIA Drivers
# ==============================================================================

Write-Header "NVIDIA Driver Setup"

# Check if NVIDIA driver is installed
$nvidiaCheck = Get-WmiObject Win32_VideoController | Where-Object { $_.Name -match "NVIDIA" }

if (-not $nvidiaCheck) {
    Write-Warn "No NVIDIA GPU detected."
    Write-Warn "GPU acceleration will not be available."
}
else {
    Write-Success "NVIDIA GPU detected: $($nvidiaCheck.Name)"
    
    Write-Host ""
    Write-Host "IMPORTANT: For WSL2 GPU support, you need the WSL2 NVIDIA driver." -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Download from: https://developer.nvidia.com/cuda/wsl/download" -ForegroundColor Cyan
    Write-Host ""
    
    $response = Read-Host "Have you already installed the WSL2 NVIDIA driver? (y/n)"
    if ($response -ne "y") {
        Write-Info "Opening NVIDIA WSL2 driver download page..."
        Start-Process "https://developer.nvidia.com/cuda/wsl/download"
        Write-Warn "Please install the driver and run this script again."
        exit 0
    }
}

# ==============================================================================
# Step 6: Install nerdctl and containerd in WSL
# ==============================================================================

Write-Header "Installing nerdctl + containerd in WSL"

Write-Info "Running installation inside WSL..."
Write-Info "This may take several minutes..."

# Create the bash script content - using single quotes to prevent PS interpretation
$bashScript = @'
#!/bin/bash
set -e

echo "=== Installing containerd and nerdctl ==="

# Update packages
sudo apt-get update

# Install containerd
sudo apt-get install -y containerd

# Create config directory
sudo mkdir -p /etc/containerd
sudo containerd config default | sudo tee /etc/containerd/config.toml > /dev/null

# Download and install nerdctl
NERDCTL_VERSION="1.7.0"
echo "Installing nerdctl v${NERDCTL_VERSION}..."
curl -fsSL "https://github.com/containerd/nerdctl/releases/download/v${NERDCTL_VERSION}/nerdctl-${NERDCTL_VERSION}-linux-amd64.tar.gz" | sudo tar -xzf - -C /usr/local/bin

# Install CNI plugins
CNI_VERSION="1.3.0"
sudo mkdir -p /opt/cni/bin
curl -fsSL "https://github.com/containernetworking/plugins/releases/download/v${CNI_VERSION}/cni-plugins-linux-amd64-v${CNI_VERSION}.tgz" | sudo tar -xzf - -C /opt/cni/bin

# Install buildkit for building images
BUILDKIT_VERSION="0.12.4"
sudo mkdir -p /usr/local/lib/buildkit
curl -fsSL "https://github.com/moby/buildkit/releases/download/v${BUILDKIT_VERSION}/buildkit-v${BUILDKIT_VERSION}.linux-amd64.tar.gz" | sudo tar -xzf - -C /usr/local/lib/buildkit

# Start containerd
sudo systemctl enable containerd
sudo systemctl start containerd

# Install NVIDIA Container Toolkit
echo "Installing NVIDIA Container Toolkit..."
DISTRO=$(lsb_release -is | tr '[:upper:]' '[:lower:]')
VERSION=$(lsb_release -rs | cut -d. -f1)
DISTRIBUTION="${DISTRO}${VERSION}"

curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg 2>/dev/null || true

echo "deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://nvidia.github.io/libnvidia-container/stable/deb/amd64 /" | sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list

sudo apt-get update
sudo apt-get install -y nvidia-container-toolkit || echo "NVIDIA toolkit install skipped (may not be available)"

# Configure containerd for NVIDIA if toolkit installed
if command -v nvidia-ctk &> /dev/null; then
    sudo nvidia-ctk runtime configure --runtime=containerd
    sudo systemctl restart containerd
    echo "NVIDIA Container Toolkit configured!"
fi

echo ""
echo "=== Installation Complete ==="
nerdctl --version
'@

# Write script to temp file
$tempFile = "$env:TEMP\install_wsl_deps.sh"
$bashScript | Out-File -FilePath $tempFile -Encoding ASCII -Force

# Convert Windows path to WSL path and run
$wslTempPath = wsl -d $WSL_DISTRO wslpath -a ($tempFile -replace "\\", "/")
wsl -d $WSL_DISTRO bash -c "tr -d '\r' < $wslTempPath > /tmp/install.sh && chmod +x /tmp/install.sh && /tmp/install.sh"

Remove-Item $tempFile -ErrorAction SilentlyContinue

Write-Success "nerdctl and containerd installed"

# ==============================================================================
# Step 7: Verification
# ==============================================================================

Write-Header "Verification"

Write-Info "Checking nerdctl..."
wsl -d $WSL_DISTRO nerdctl --version

Write-Info "Checking containerd..."
wsl -d $WSL_DISTRO sudo ctr version

Write-Info "Checking GPU access..."
$gpuCheck = wsl -d $WSL_DISTRO nvidia-smi 2>&1
if ($gpuCheck -match "NVIDIA-SMI") {
    Write-Success "GPU accessible in WSL2!"
}
else {
    Write-Warn "GPU not accessible yet. This is normal if driver was just installed."
    Write-Warn "Try: wsl --shutdown, then reopen WSL."
}

# ==============================================================================
# Complete
# ==============================================================================

Write-Header "Setup Complete!"

Write-Host ""
Write-Host "Your Local Mind environment is ready!" -ForegroundColor Green
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Cyan
Write-Host "  1. Open Ubuntu (WSL2):"
Write-Host "     > wsl -d $WSL_DISTRO"
Write-Host ""
Write-Host "  2. Navigate to your project:"
Write-Host "     cd /mnt/d/'Projects Workspace'/'Local Notebooklm'"
Write-Host ""
Write-Host "  3. Start the stack:"
Write-Host "     bash scripts/init.sh"
Write-Host ""
Write-Host "  4. Open http://localhost:3000"
Write-Host ""
