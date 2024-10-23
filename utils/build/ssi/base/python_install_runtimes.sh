#!/bin/bash
if [ -f /etc/debian_version ] || [ "$DISTRIBUTION" = "Debian" ] || [ "$DISTRIBUTION" = "Ubuntu" ]; then
    OS="Debian"
elif [ -f /etc/redhat-release ] || [ "$DISTRIBUTION" = "RedHat" ] || [ "$DISTRIBUTION" = "CentOS" ] || [ "$DISTRIBUTION" = "Amazon" ] || [ "$DISTRIBUTION" = "Rocky" ] || [ "$DISTRIBUTION" = "AlmaLinux" ]; then
    OS="RedHat"
# Some newer distros like Amazon may not have a redhat-release file
elif [ -f /etc/system-release ] || [ "$DISTRIBUTION" = "Amazon" ]; then
    OS="RedHat"
# Arista is based off of Fedora14/18 but do not have /etc/redhat-release
elif [ -f /etc/Eos-release ] || [ "$DISTRIBUTION" = "Arista" ]; then
    OS="RedHat"
# openSUSE and SUSE use /etc/SuSE-release or /etc/os-release
elif [ -f /etc/SuSE-release ] || [ "$DISTRIBUTION" = "SUSE" ] || [ "$DISTRIBUTION" = "openSUSE" ]; then
    OS="SUSE"
elif [ -f /etc/alpine-release ]; then
    OS="Alpine"
fi

if [ "$OS" = "Debian" ]; then
    #Install pyenv
    packages_install="make build-essential libssl-dev zlib1g-dev libbz2-dev libreadline-dev libsqlite3-dev git curl llvm libncursesw5-dev xz-utils tk-dev tzdata libxml2-dev libxmlsec1-dev libffi-dev liblzma-dev"
    # shellcheck disable=SC2086
    apt-get install -y $packages_install || ln -fs /usr/share/zoneinfo/America/New_York /etc/localtime && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends $packages_install
    export PYENV_ROOT="~/.pyenv"
    curl https://pyenv.run | bash
    export PATH="$PYENV_ROOT/bin:$PATH"
    eval "$(pyenv init -)"
    export PATH="~/.pyenv/bin:$PATH" && eval "$(pyenv init -)" && pyenv install "$PY_VERSION" && pyenv global "$PY_VERSION"

elif [ "$OS" = "RedHat" ]; then
    yum install -y python3
else
    echo "Unknown OS"
    exit 1
fi
