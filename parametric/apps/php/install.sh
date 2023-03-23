#!/bin/bash

# This script installs the PHP library
# It first looks at the /binaries directory to see if there is a file matching "datadog-php-tracer-*.tar.gz"
# If there is no package in /binaries then the binaries are pulled from the specified release

DDTRACE_VERSION=0.84.0
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
  # curl -LO https://github.com/DataDog/dd-trace-php/releases/download/${DDTRACE_VERSION}/datadog-setup.php
  curl -LO https://output.circle-artifacts.com/output/job/b4a03600-2305-4605-827e-0d8daaaf8785/artifacts/0/datadog-setup.php 
  SETUP=datadog-setup.php
fi
echo "Installing php package $PKG with setup script $SETUP"
php $SETUP --php-bin=all "$([ "$PKG" = "" ] || echo --file="$PKG")"
