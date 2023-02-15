#!/bin/bash

ARCH=$(uname -m | sed 's/x86_//;s/i[3-6]86/32/')
if [ "$ARCH" = "arm64" ]; then
  ARCH=aarch64
else
  ARCH=x86_64
fi
curl -LO https://output.circle-artifacts.com/output/job/66a59769-7785-4db4-af6c-36a905218db1/artifacts/0/dd-library-php-1.0.0-nightly-${ARCH}-linux-gnu.tar.gz
curl -LO https://github.com/DataDog/dd-trace-php/releases/download/0.84.0/datadog-setup.php
php datadog-setup.php --php-bin=all --file="$(find . -maxdepth 1 -name 'datadog-php-tracer-*.tar.gz')"
