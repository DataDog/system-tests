#!/bin/bash

set -eu
set -o pipefail
set -x

function fetch_version {
  declare -r what=$1
  strings /usr/lib/nginx/modules/ngx_http_datadog_module.so | \
    grep -F "[${what} version" | \
    sed 's/.* version \([^]]\+\).*/\1/'
}

function epilogue {
  local module_version=$1
  if [[ -z $module_version ]]; then
    echo "ERROR: Missing module version."
    exit 1
  fi

  if [[ $module_version = unknown_mod_version ]]; then
    module_version=v$(fetch_version nginx_mod)
    if [[ $module_version == v ]]; then
      echo "ERROR: could not determine module version"
      exit 1
    fi
  fi

  echo "DataDog/nginx-datadog version: ${module_version}"
  echo "$module_version" | tr -d v > SYSTEM_TESTS_LIBRARY_VERSION

  rm -f /etc/nginx/nginx.conf
  if version_first_is_greater "$module_version" "v1.1.0"; then
    ln -s nginx.conf.waf /etc/nginx/nginx.conf
    fetch_version libddwaf > SYSTEM_TESTS_LIBDDWAF_VERSION
    fetch_version waf_rules > SYSTEM_TESTS_APPSEC_EVENT_RULES_VERSION
  else
    ln -s nginx.conf.no-waf /etc/nginx/nginx.conf
    echo "0.0.0" > SYSTEM_TESTS_LIBDDWAF_VERSION
    echo "0.0.0" > SYSTEM_TESTS_APPSEC_EVENT_RULES_VERSION
  fi

}

version_first_is_greater() {
    local v1=(${1//./ })
    local v2=(${2//./ })

    # Remove the 'v' prefix from the version numbers
    v1[0]=${v1[0]//v/}
    v2[0]=${v2[0]//v/}

    # Compare the major, minor, and patch numbers
    for i in {0..2}; do
        if (( v1[i] > v2[i] )); then
            return 0
        elif (( v1[i] < v2[i] )); then
            return 1
        fi
    done

    # equal (not greater)
    return 1
}

if [[ $(find /builds -name 'ngx_http_datadog_module-*.so.tgz' | wc -l) -gt 0 ]]; then
  echo "Found module in /builds"

  if [[ $(find /builds -name 'ngx_http_datadog_module-*.so.tgz' | wc -l) -gt 1 ]]; then
    echo "ERROR: Found several ngx_http_datadog_module-*.so.tgz files in builds/, abort."
    exit 1
  fi

  NGINX_VERSION_OF_MODULE=$(find /builds -name 'ngx_http_datadog_module-*.so.tgz' | grep -Po '(\d+\.\d+\.\d+)')
  if [[ $NGINX_VERSION_OF_MODULE != $NGINX_VERSION ]]; then
    echo "ERROR: nginx mismatch: module for $NGINX_VERSION_OF_MODULE, but base image of $NGINX_VERSION"
    exit 1
  fi

  MAIN_TARBALL=$(find /builds -name 'ngx_http_datadog_module-*.so.tgz')
  tar -xzvf "$MAIN_TARBALL" -C /usr/lib/nginx/modules
  if [[ $(find /builds -name 'ngx_http_datadog_module-*.so.debug.tgz' | wc -l) -eq 1 ]]; then
    tar -xzvf /builds/ngx_http_datadog_module-*.so.debug.tgz -C /usr/lib/nginx/modules
  fi

  epilogue unknown_mod_version
  exit 0
fi

if [[ -f /builds/ngx_http_datadog_module.so ]]; then
  cp -v /builds/ngx_http_datadog_module.so /usr/lib/nginx/modules
  if [[ -f /builds/ngx_http_datadog_module.so.debug ]]; then
    cp -v /builds/ngx_http_datadog_module.so.debug /usr/lib/nginx/modules
  fi

  epilogue unknown_mod_version
  exit 0
fi

get_latest_release() {
    wget -qO- "https://api.github.com/repos/DataDog/nginx-datadog/releases/latest" \
      | jq -r '.tag_name'
}

get_architecture() {
  arch | sed 's/x86_64/amd64/' | sed 's/aarch64/arm64/'
}


if [ NGINX_VERSION == "" ]; then
  echo 1>&2 "ERROR: Missing NGINX_VERSION."
  exit 1
fi

readonly ARCH=$(get_architecture)

if [[ $ARCH != "amd64" && $ARCH != "arm64" ]]; then
    echo 1>&2 "ERROR: Architecture ${ARCH} is not supported."
    exit 1
fi

readonly NGINX_DATADOG_VERSION="$(get_latest_release)"

if version_first_is_greater "$NGINX_DATADOG_VERSION" "v1.1.0"; then
  TARBALLS=(
    "ngx_http_datadog_module-appsec-${ARCH}-${NGINX_VERSION}.so.tgz"
    "ngx_http_datadog_module-appsec-${ARCH}-${NGINX_VERSION}.so.debug.tgz"
  )
  for FILE in "${TARBALLS[@]}"; do
    wget -O - \
      "https://github.com/DataDog/nginx-datadog/releases/download/$NGINX_DATADOG_VERSION/${FILE}" \
      | tar -xzf - -C /usr/lib/nginx/modules
  done
else
  # old versions
  BASE_IMAGE="nginx:${NGINX_VERSION}"
  BASE_IMAGE_WITHOUT_COLONS=$(echo "$BASE_IMAGE" | tr ':' '_')
  TARBALL="$BASE_IMAGE_WITHOUT_COLONS-$ARCH-ngx_http_datadog_module.so.tgz"

  # Install NGINX plugin
  wget "https://github.com/DataDog/nginx-datadog/releases/download/${NGINX_DATADOG_VERSION}/${TARBALL}"
  tar -xzf "${TARBALL}" -C /usr/lib/nginx/modules
  rm "$TARBALL"
fi

epilogue "${NGINX_DATADOG_VERSION:1}"
