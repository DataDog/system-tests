#!/bin/bash

declare -r ARCH="$1"

if [[ "$(cat /etc/redhat-release || true)" == "Red Hat Enterprise Linux release 8."* ]]; then
    OS="RedHat_8"
elif [ -f /etc/debian_version ] || [ "$DISTRIBUTION" = "Debian" ] || [ "$DISTRIBUTION" = "Ubuntu" ]; then
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

if [ "$OS" = "RedHat_8" ]; then
    yum install -y which zip unzip wget
elif [ "$OS" = "RedHat" ]; then
    # Update the repo URLs, since July 2024 we need to use vault for CentOS 7
    if [ "${ARCH}" != "amd64" ]; then
        repo_version="altarch/7.9.2009"
    else
        repo_version="7.9.2009"
    fi

    cat << EOF > /etc/yum.repos.d/CentOS-Base.repo
[base]
name=CentOS-\$releasever - Base
baseurl=http://vault.centos.org/${repo_version}/os/\$basearch/
gpgcheck=0

[updates]
name=CentOS-\$releasever - Updates
baseurl=http://vault.centos.org/${repo_version}/updates/\$basearch/
gpgcheck=0

[extras]
name=CentOS-\$releasever - Extras
baseurl=http://vault.centos.org/${repo_version}/extras/\$basearch/
gpgcheck=0

[centosplus]
name=CentOS-\$releasever - Plus
baseurl=http://vault.centos.org/${repo_version}/centosplus/\$basearch/
gpgcheck=0
enabled=0
EOF
    yum install -y which zip unzip wget
elif [ "$OS" = "Debian" ]; then
    apt-get update
    apt-get install --yes curl zip unzip wget
elif [ "$OS" =  "Alpine" ]; then
    apk add -U curl bash
else
    echo "Unknown OS"
    exit 1
fi
