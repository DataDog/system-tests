#!/bin/bash

set -e

declare -r RUNTIME_VERSIONS="$1"

echo "Installing .NET runtime versions: $RUNTIME_VERSIONS"

# Download the .NET install script once
curl -sSL https://dot.net/v1/dotnet-install.sh --output dotnet-install.sh
chmod +x ./dotnet-install.sh

# Install each .NET version specified (comma-separated)
for VERSION in $(echo "$RUNTIME_VERSIONS" | tr ',' ' '); do
    echo "Installing .NET version: $VERSION"
    ./dotnet-install.sh --version "$VERSION" --install-dir /usr/share/dotnet
done

# Clean up install script
rm ./dotnet-install.sh

# Create symlinks to make dotnet available globally
ln -sf /usr/share/dotnet/dotnet /usr/bin/dotnet

# Verify installation
echo "=== .NET Installation Verification ==="
echo ".NET version: $(dotnet --version)"
echo "Available SDKs:"
dotnet --list-sdks
echo "Available runtimes:"
dotnet --list-runtimes
