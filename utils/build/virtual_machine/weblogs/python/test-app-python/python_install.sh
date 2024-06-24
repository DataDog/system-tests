#!/bin/bash

DISTRO=$1
PY_VERSION=$2

#Workaround: if python install pyenv
if [ "$DISTRO" = "deb" ]; then
    #Install pyenv
    packages_install="make build-essential libssl-dev zlib1g-dev libbz2-dev libreadline-dev libsqlite3-dev git curl llvm libncursesw5-dev xz-utils tk-dev tzdata libxml2-dev libxmlsec1-dev libffi-dev liblzma-dev"
    # shellcheck disable=SC2086
    sudo apt-get install -y $packages_install || ln -fs /usr/share/zoneinfo/America/New_York /etc/localtime && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends "$packages_install"
    export PYENV_ROOT="/home/datadog/.pyenv"
    sudo curl https://pyenv.run | bash
    export PATH="$PYENV_ROOT/bin:$PATH"
    eval "$(pyenv init -)"
else
    #Install pyenv
    sudo yum install -y gcc zlib-devel bzip2 bzip2-devel readline-devel sqlite sqlite-devel openssl-devel tk-devel libffi-devel git
    git clone https://github.com/pyenv/pyenv.git /home/datadog/.pyenv
    export PYENV_ROOT="/home/datadog/.pyenv"
    export PATH="$PYENV_ROOT/bin:$PATH"
    eval "$(pyenv init -)"
fi

export PATH="/home/datadog/.pyenv/bin:$PATH" && eval "$(pyenv init -)" && pyenv install "$PY_VERSION" && pyenv global "$PY_VERSION"
