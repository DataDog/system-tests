#!/bin/bash

set -e

declare -r RUNTIME_VERSIONS="$1"

echo "Installing Ruby runtime versions: $RUNTIME_VERSIONS"

# Detect OS
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

# Install dependencies based on OS
if [ "$OS" = "Debian" ]; then
    apt-get update
    ln -fs /usr/share/zoneinfo/America/New_York /etc/localtime
    DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        make build-essential libssl-dev zlib1g-dev libbz2-dev libreadline-dev \
        libsqlite3-dev git curl llvm libncursesw5-dev xz-utils tk-dev tzdata \
        libxml2-dev libxmlsec1-dev libffi-dev liblzma-dev libgdbm-dev \
        libgdbm-compat-dev libyaml-dev
elif [ "$OS" = "RedHat" ]; then
    yum groupinstall -y 'Development Tools'
    yum install -y openssl-devel readline-devel zlib-devel sqlite-devel \
        libyaml-devel libffi-devel git curl
else
    echo "Unknown OS: $OS"
    exit 1
fi

# Install rbenv and ruby-build
export RBENV_ROOT="/usr/local/rbenv"
export PATH="$RBENV_ROOT/bin:$PATH"

# Clone rbenv
git clone https://github.com/rbenv/rbenv.git "$RBENV_ROOT"

# Clone ruby-build plugin
mkdir -p "$RBENV_ROOT/plugins"
git clone https://github.com/rbenv/ruby-build.git "$RBENV_ROOT/plugins/ruby-build"

# Initialize rbenv
eval "$(rbenv init -)"

# Install each Ruby version specified (comma-separated)
for VERSION in $(echo "$RUNTIME_VERSIONS" | tr ',' ' '); do
    echo "Installing Ruby version: $VERSION"
    rbenv install "$VERSION"
done

# Set the first version as global (or default if only one)
FIRST_VERSION=$(echo "$RUNTIME_VERSIONS" | cut -d',' -f1)
rbenv global "$FIRST_VERSION"

# Install bundler for all versions
for VERSION in $(echo "$RUNTIME_VERSIONS" | tr ',' ' '); do
    echo "Installing bundler for Ruby $VERSION"
    rbenv shell "$VERSION"
    gem install bundler
done

# Reset to global version
rbenv shell "$FIRST_VERSION"

# Create symlinks for global access
ln -sf "$RBENV_ROOT/shims/ruby" /usr/bin/ruby
ln -sf "$RBENV_ROOT/shims/gem" /usr/bin/gem
ln -sf "$RBENV_ROOT/shims/bundle" /usr/bin/bundle
ln -sf "$RBENV_ROOT/shims/rails" /usr/bin/rails

# Make rbenv available in shell
echo 'export RBENV_ROOT="/usr/local/rbenv"' >> /etc/profile.d/rbenv.sh
echo 'export PATH="$RBENV_ROOT/bin:$PATH"' >> /etc/profile.d/rbenv.sh
echo 'eval "$(rbenv init -)"' >> /etc/profile.d/rbenv.sh

# Verify installation
echo "=== Ruby Installation Verification ==="
echo "Ruby version: $(ruby --version)"
echo "Gem version: $(gem --version)"
echo "Bundler version: $(bundle --version)"
echo "Available Ruby versions:"
rbenv versions