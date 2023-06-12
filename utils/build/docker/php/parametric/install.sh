#!/bin/bash

# This script installs the PHP library
# It first looks at the /binaries directory to see if there is a file matching "datadog-php-tracer-*.tar.gz"
# If there is no package in /binaries then the binaries are pulled from the specified release

PKG=$(find /binaries -maxdepth 1 -name 'dd-library-php-*-gnu.tar.gz')
SETUP=/binaries/datadog-setup.php

if [ "$PKG" != "" ] && [ ! -f "$SETUP" ]; then
  echo "local install failed: package located in /binaries but datadog-setup.php not present, please include it"
  exit 1
fi

if [ "$PKG" == "" ]; then
  ARCH=$(uname -m | sed 's/x86_//;s/i[3-6]86/32/')
  if [ "$ARCH" = "arm64" ]; then
    ARCH=aarch64
  else
    ARCH=x86_64
  fi
  curl -LO https://github.com/DataDog/dd-trace-php/releases/latest/download/datadog-setup.php
  SETUP=datadog-setup.php
fi
echo "Installing php package $PKG with setup script $SETUP"
php $SETUP --php-bin=all "$([ "$PKG" = "" ] || echo --file="$PKG")"
