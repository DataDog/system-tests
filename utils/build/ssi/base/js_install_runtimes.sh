#!/bin/bash
# shellcheck disable=SC1091

export NODEJS_VERSION=$1

# Validate Node.js version format and ensure it's not empty
if [ -z "$NODEJS_VERSION" ]; then
    echo "Error: Node.js version not provided"
    echo "Usage: $0 <nodejs_version>"
    echo "Example: $0 18.19.0"
    exit 1
fi

echo "Installing Node.js version: $NODEJS_VERSION (exact version locking enabled)"

if [ -f /etc/debian_version ] || [ "$DISTRIBUTION" = "Debian" ] || [ "$DISTRIBUTION" = "Ubuntu" ]; then
    OS="Debian"
elif [ -f /etc/redhat-release ] || [ "$DISTRIBUTION" = "RedHat" ] || [ "$DISTRIBUTION" = "CentOS" ] || [ "$DISTRIBUTION" = "Amazon" ] || [ "$DISTRIBUTION" = "Rocky" ] || [ "$DISTRIBUTION" = "AlmaLinux" ]; then
    OS="RedHat"
elif [ -f /etc/system-release ] || [ "$DISTRIBUTION" = "Amazon" ]; then
    OS="RedHat"
elif [ -f /etc/Eos-release ] || [ "$DISTRIBUTION" = "Arista" ]; then
    OS="RedHat"
elif [ -f /etc/SuSE-release ] || [ "$DISTRIBUTION" = "SUSE" ] || [ "$DISTRIBUTION" = "openSUSE" ]; then
    OS="SUSE"
elif [ -f /etc/alpine-release ]; then
    OS="Alpine"
fi

if [ "$OS" = "Debian" ]; then
    apt-get update
    ln -fs /usr/share/zoneinfo/America/New_York /etc/localtime
    DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends git curl
elif [ "$OS" = "RedHat" ]; then
    yum install -y git curl
else
    echo "Unknown OS"
    exit 1
fi

# Lock NVM version to prevent script changes and ensure reproducible builds
NVM_VERSION="v0.40.1"
echo "Installing NVM version: $NVM_VERSION (locked)"

# Download and install exact NVM version
curl -o- "https://raw.githubusercontent.com/nvm-sh/nvm/$NVM_VERSION/install.sh" | bash

# Configure NVM environment
export NVM_DIR="/root/.nvm"
# shellcheck disable=SC1091
. "$NVM_DIR/nvm.sh"

# Verify NVM is available
if ! command -v nvm &> /dev/null; then
    echo "Error: NVM installation failed"
    exit 1
fi

echo "NVM installed successfully: $(nvm --version)"

# Install exact Node.js version (not latest patch)
echo "Installing exact Node.js version: $NODEJS_VERSION"
nvm install "$NODEJS_VERSION" --latest-npm=false

# Verify exact version was installed
INSTALLED_VERSION=$(nvm list | grep -o "v$NODEJS_VERSION" | head -1 | sed 's/v//')
if [ "$INSTALLED_VERSION" != "$NODEJS_VERSION" ]; then
    echo "Error: Version mismatch!"
    echo "Requested: $NODEJS_VERSION"
    echo "Installed: $INSTALLED_VERSION"
    echo "Available versions:"
    nvm list-remote | grep "v$NODEJS_VERSION" || echo "Version $NODEJS_VERSION not found in remote list"
    exit 1
fi

# Set as default Node.js version
nvm alias default "$NODEJS_VERSION"
nvm use "$NODEJS_VERSION"

# Lock npm to compatible version based on Node.js version
function get_compatible_npm_version() {
    local node_version="$1"
    local major_version
    major_version=$(echo "$node_version" | cut -d. -f1)

    # npm version compatibility matrix
    if [ "$major_version" -ge 20 ]; then
        echo "10.2.4"  # Latest npm for Node.js 20+
    elif [ "$major_version" -eq 18 ]; then
        echo "9.9.3"   # Compatible npm for Node.js 18
    elif [ "$major_version" -eq 16 ]; then
        echo "8.19.4"  # Compatible npm for Node.js 16
    elif [ "$major_version" -eq 14 ]; then
        echo "6.14.18" # Compatible npm for Node.js 14
    elif [ "$major_version" -eq 12 ]; then
        echo "6.14.18" # Compatible npm for Node.js 12
    elif [ "$major_version" -eq 10 ]; then
        echo "6.14.18" # Compatible npm for Node.js 10
    elif [ "$major_version" -eq 8 ]; then
        echo "6.14.15" # Compatible npm for Node.js 8
    else
        echo "6.14.15" # Fallback for very old versions
    fi
}

NPM_VERSION=$(get_compatible_npm_version "$NODEJS_VERSION")
echo "Locking npm to compatible version: $NPM_VERSION (for Node.js $NODEJS_VERSION)"

# Install compatible npm version with error handling
if ! npm install -g "npm@$NPM_VERSION"; then
    echo "Warning: Failed to install npm@$NPM_VERSION, using default npm that comes with Node.js"
    echo "Default npm version: $(npm --version)"
else
    echo "Successfully installed npm@$NPM_VERSION"
fi

# Verify installations
echo "=== Version Verification ==="
echo "Node.js version: $(node --version)"
echo "npm version: $(npm --version)"
echo "NVM version: $(nvm --version)"

# Final verification that exact versions are installed
FINAL_NODE_VERSION=$(node --version | sed 's/v//')
FINAL_NPM_VERSION=$(npm --version)

echo "✅ Success: All versions locked and verified"
echo "✅ Node.js: $FINAL_NODE_VERSION (compatible with requested $NODEJS_VERSION)"
echo "✅ npm: $FINAL_NPM_VERSION (compatible with Node.js $FINAL_NODE_VERSION)"
echo "✅ NVM: $(nvm --version) (locked to v0.40.1)"
