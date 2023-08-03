#!/bin/bash
DISTRO=$1
PY_VERSION=$2

#Workaround: if python install pyenv
if [ "$DISTRO" = "deb" ]; then
    #Install pyenv
    sudo apt-get install -y make build-essential libssl-dev zlib1g-dev libbz2-dev libreadline-dev libsqlite3-dev wget curl llvm libncursesw5-dev xz-utils tk-dev libxml2-dev libxmlsec1-dev libffi-dev liblzma-dev
    curl https://pyenv.run | bash
    export PYENV_ROOT="$HOME/.pyenv"
    export PATH="$PYENV_ROOT/bin:$PATH"
    eval "$(pyenv init -)"
 else
    #Install pyenv
    sudo yum install -y gcc zlib-devel bzip2 bzip2-devel readline-devel sqlite sqlite-devel openssl-devel tk-devel libffi-devel git
    git clone https://github.com/pyenv/pyenv.git ~/.pyenv
    export PYENV_ROOT="$HOME/.pyenv"
    export PATH="$PYENV_ROOT/bin:$PATH"
     eval "$(pyenv init -)"
 fi


export PATH="~/.pyenv/bin:$PATH" && eval "$(pyenv init -)" && pyenv install "$PY_VERSION" && pyenv global "$PY_VERSION"