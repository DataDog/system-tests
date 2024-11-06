#!/bin/bash

export DOTNET_VERSION=$1

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
    ln -fs /usr/share/zoneinfo/America/New_York /etc/localtime
    DEBIAN_FRONTEND=noninteractive
    apt-get install -y --no-install-recommends make build-essential libssl-dev zlib1g-dev libbz2-dev libreadline-dev libsqlite3-dev git curl llvm libncursesw5-dev xz-utils tk-dev tzdata libxml2-dev libxmlsec1-dev libffi-dev liblzma-dev libyaml-dev
    wget https://packages.microsoft.com/config/debian/11/packages-microsoft-prod.deb -O packages-microsoft-prod.deb
    dpkg -i packages-microsoft-prod.deb
    rm packages-microsoft-prod.deb
    apt-get update
    apt install -y apt-transport-https
    apt install -y dotnet-sdk-"$DOTNET_VERSION"
    apt-get install -y aspnetcore-runtime-"$DOTNET_VERSION"
    apt-get install -y dotnet-runtime-"$DOTNET_VERSION"
elif [ "$OS" = "RedHat" ]; then
    dnf install dotnet-sdk-"$DOTNET_VERSION" aspnetcore-runtime-"$DOTNET_VERSION"
else
    echo "Unknown OS"
    exit 1
fi
