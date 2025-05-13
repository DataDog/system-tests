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

FILENAME=ngx_http_datadog_module-appsec-$ARCH-$NGINX_VERSION.so

if [ -f "$FILENAME" ]; then
  echo "Install NGINX plugin from binaries/$FILENAME"
  cp $FILENAME /usr/lib/nginx/modules/ngx_http_datadog_module.so
  NGINX_DATADOG_VERSION="v99.99.99"  # TODO: get version from the binary. Right now, use the "big-version" trick
else
  NGINX_DATADOG_VERSION="$(get_latest_release DataDog/nginx-datadog)"
  TARBALL="$FILENAME.tgz"
  echo "Get NGINX plugin from last github release of nginx-datadog"
  wget "https://github.com/DataDog/nginx-datadog/releases/download/${NGINX_DATADOG_VERSION}/${TARBALL}"
  tar -xzf "${TARBALL}" -C /usr/lib/nginx/modules
  rm "$TARBALL"
fi

echo '{"status": "ok", "library": {"name": "cpp_nginx", "version": "'$NGINX_DATADOG_VERSION'"}}' > /builds/healthcheck.json
cat /builds/healthcheck.json

