#!/bin/sh

set -eu

export RB_VERSION="$1"

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

case "$RB_VERSION" in
    3.4.*)
        RB_YJIT=1
        ;;
    4.*)
        RB_YJIT=1
        ;;
esac

if [ -n "$RB_YJIT" ]; then
    case "$(uname -m)" in
        'x86_64')
            rustArch='x86_64-unknown-linux-gnu'
            rustupUrl='https://static.rust-lang.org/rustup/archive/1.26.0/x86_64-unknown-linux-gnu/rustup-init'
            rustupSha256='0b2f6c8f85a3d02fde2efc0ced4657869d73fccfce59defb4e8d29233116e6db'
            ;;
        'aarch64')
            rustArch='aarch64-unknown-linux-gnu'
            rustupUrl='https://static.rust-lang.org/rustup/archive/1.26.0/aarch64-unknown-linux-gnu/rustup-init'
            rustupSha256='673e336c81c65e6b16dcdede33f4cc9ed0f08bde1dbe7a935f113605292dc800'
            ;;
    esac

    if [ -n "$rustArch" ]; then
        mkdir -p /tmp/rust

        curl -o /tmp/rust/rustup-init "$rustupUrl"
        echo "$rustupSha256 */tmp/rust/rustup-init" | sha256sum --check --strict
        chmod +x /tmp/rust/rustup-init

        export RUSTUP_HOME='/tmp/rust/rustup' CARGO_HOME='/tmp/rust/cargo'
        export PATH="$CARGO_HOME/bin:$PATH"
        /tmp/rust/rustup-init -y --no-modify-path --profile minimal --default-toolchain '1.74.1' --default-host "$rustArch"

        rustc --version
        cargo --version
    fi
fi

if [ "$OS" = "Debian" ]; then
    apt-get update
    ln -fs /usr/share/zoneinfo/America/New_York /etc/localtime
    DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends make build-essential libssl-dev zlib1g-dev libbz2-dev libreadline-dev libsqlite3-dev git curl llvm libncursesw5-dev xz-utils tk-dev tzdata libxml2-dev libxmlsec1-dev libffi-dev liblzma-dev libyaml-dev

elif [ "$OS" = "RedHat" ]; then
    yum install -y curl gcc gcc-c++ gettext make patchutils patch libtool pkgconfig gettext file zip unzip git xz gcc automake bison zlib-devel libyaml-devel openssl-devel gdbm-devel readline-devel ncurses-devel libffi-devel
else
    echo "Unknown OS"
    exit 1
fi

# install rbenv: https://github.com/rbenv/rbenv
git clone https://github.com/rbenv/rbenv.git ~/.rbenv

# set up basic rbenv things
RBENV_ROOT="$HOME/.rbenv"
PATH="$RBENV_ROOT/bin:$PATH"
eval "$(rbenv init -)"

# isntall ruby-build plugin: https://github.com/rbenv/ruby-build
git clone https://github.com/rbenv/ruby-build.git "$(rbenv root)"/plugins/ruby-build

rbenv install "$RB_VERSION"
rbenv global "$RB_VERSION"
