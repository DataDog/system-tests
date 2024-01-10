#!/bin/bash
DISTRO=$1
PY_VERSION=$2

#Workaround: if python install pyenv
if [ "$DISTRO" = "deb" ]; then
    #Install pyenv
    sudo apt-get install -y make build-essential libssl-dev zlib1g-dev libbz2-dev libreadline-dev libsqlite3-dev wget curl llvm libncursesw5-dev xz-utils tk-dev libxml2-dev libxmlsec1-dev libffi-dev liblzma-dev
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