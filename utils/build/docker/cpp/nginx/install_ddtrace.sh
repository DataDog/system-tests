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

ARCH=$(get_architecture)

if [ -z "$ARCH" ]; then
    echo 1>&2 "ERROR: Architecture $(uname -m) is not supported."
    exit 1
fi

# NGINX_VERSION=1.17.3
NGINX_VERSION=1.25.2

RELEASE_TAG="$(get_latest_release DataDog/nginx-datadog)"

echo "DataDog/nginx-datadog version: $RELEASE_TAG"
echo $RELEASE_TAG > SYSTEM_TESTS_LIBRARY_VERSION
touch SYSTEM_TESTS_LIBDDWAF_VERSION
echo "0.0.0" > SYSTEM_TESTS_APPSEC_EVENT_RULES_VERSION

# Install Datadog NGINX plugin
# tarball="nginx_${NGINX_VERSION}-${ARCH}-ngx_http_datadog_module.so.tgz"
# wget "https://github.com/DataDog/nginx-datadog/releases/download/$RELEASE_TAG/$tarball"
# tar -xzf "$tarball" -C /usr/lib/nginx/modules
# rm "$tarball"
if [ "$ARCH" == "arm64" ]; then
  wget -P /usr/lib/nginx/modules https://output.circle-artifacts.com/output/job/575ee617-d5e9-4aaf-98bb-37b063ffd318/artifacts/0/ngx_http_datadog_module.so
else
  wget -P /usr/lib/nginx/modules https://output.circle-artifacts.com/output/job/ac040abb-5da9-4d9b-968d-2924beff3e2c/artifacts/0/ngx_http_datadog_module.so
fi

echo "Library version : $(cat SYSTEM_TESTS_LIBRARY_VERSION)"
