#!/bin/bash

export DOTNET_VERSION=$1
set -e

curl -sSL https://dot.net/v1/dotnet-install.sh --output dotnet-install.sh  \
    && chmod +x ./dotnet-install.sh \
    && ./dotnet-install.sh --version $DOTNET_VERSION --install-dir /usr/share/dotnet \
    && rm ./dotnet-install.sh \
    && ln -s /usr/share/dotnet/dotnet /usr/bin/dotnet
