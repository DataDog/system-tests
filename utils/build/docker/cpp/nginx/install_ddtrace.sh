#!/bin/bash

set -eu

get_latest_release() {
    wget -qO- "https://api.github.com/repos/$1/releases/latest" | jq -r '.tag_name'
}

get_architecture() {
  case "$(uname -m)" in
    aarch64)
      echo "arm64"
      ;;
    arm64)
      echo "arm64"
      ;;
    x86_64)
      echo "amd64"
      ;;
    amd64)
      echo "amd64"
      ;;
    *)
      echo ""
      ;;
  esac
}

if [ NGINX_VERSION == "" ]; then
  echo 1>&2 "ERROR: Missing NGINX_VERSION."
  exit 1
fi

ARCH=$(get_architecture)

if [ -z "$ARCH" ]; then
    echo 1>&2 "ERROR: Architecture $(uname -m) is not supported."
    exit 1
fi

NGINX_DATADOG_VERSION="$(get_latest_release DataDog/nginx-datadog)"

BASE_IMAGE="nginx:${NGINX_VERSION}"
BASE_IMAGE_WITHOUT_COLONS=$(echo "$BASE_IMAGE" | tr ':' '_')
TARBALL="$BASE_IMAGE_WITHOUT_COLONS-$ARCH-ngx_http_datadog_module.so.tgz"

# Install NGINX plugin
wget "https://github.com/DataDog/nginx-datadog/releases/download/${NGINX_DATADOG_VERSION}/${TARBALL}"
tar -xzf "${TARBALL}" -C /usr/lib/nginx/modules
rm "$TARBALL"

# Sys test stuff
echo "DataDog/nginx-datadog version: ${NGINX_DATADOG_VERSION}"
echo $NGINX_DATADOG_VERSION > SYSTEM_TESTS_LIBRARY_VERSION
touch SYSTEM_TESTS_LIBDDWAF_VERSION
echo "0.0.0" > SYSTEM_TESTS_APPSEC_EVENT_RULES_VERSION
echo "Library version : $(cat SYSTEM_TESTS_LIBRARY_VERSION)"
