#!/bin/bash

# This script installs the PHP library
# It first looks at the /binaries directory to see if there is a file matching "datadog-php-tracer-*.tar.gz"
# If there is no package in /binaries then the binaries are pulled from

DDTRACE_VERSION=0.84.0
PKG=$(find /binaries -maxdepth 1 -name 'datadog-php-tracer-*.tar.gz')
SETUP=/binaries/datadog-setup.php

if [ "$PKG" != "" ] && [ ! -f "$SETUP_FILE" ]; then
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
  curl -LO https://github.com/DataDog/dd-trace-php/releases/download/${DDTRACE_VERSION}/datadog-setup.php
  curl -LO https://github.com/DataDog/dd-trace-php/releases/download/${DDTRACE_VERSION}/dd-library-php-${DDTRACE_VERSION}-${ARCH}-linux-gnu.tar.gz
  # curl -LO https://output.circle-artifacts.com/output/job/66a59769-7785-4db4-af6c-36a905218db1/artifacts/0/dd-library-php-1.0.0-nightly-${ARCH}-linux-gnu.tar.gz
  # curl -LO https://github.com/DataDog/dd-trace-php/releases/download/0.84.0/datadog-setup.php
  PKG=dd-library-php-${DDTRACE_VERSION}-${ARCH}-linux-gnu.tar.gz
  SETUP=datadog-setup.php
fi
echo "Installing php package $PKG with setup script $SETUP"
php $SETUP --php-bin=all --file="$PKG"
