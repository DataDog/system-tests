#!/bin/bash
set -eu

# shellcheck source=/dev/null
source "$(dirname "$0")/github.sh"

FILENAME=mod_datadog.so
DEST_FOLDER=/usr/lib/apache2/modules

cd /binaries

if [ -f "$FILENAME" ]; then
  echo "Install HTTPD plugin from binaries/$FILENAME"
  HTTPD_DATADOG_VERSION="v99.99.99"  # TODO: get version from the binary. Right now, use the "big-version" trick
  cp "$FILENAME" "$DEST_FOLDER/$FILENAME"
elif [ -f cpp-httpd-github-actions-artifact.json ]; then
  echo "Install HTTPD plugin from staged GitHub Actions artifact metadata"
  auth_header=$(get_authentication_header)
  ARCHIVE_URL=$(jq -r '.archive_download_url' cpp-httpd-github-actions-artifact.json)
  curl_cmd="curl -Lf $auth_header -o mod_datadog_artifact.zip ${ARCHIVE_URL}"
  eval "$curl_cmd"
  mkdir -p /tmp/mod-datadog-artifact
  unzip -o mod_datadog_artifact.zip -d /tmp/mod-datadog-artifact
  cp "$(find /tmp/mod-datadog-artifact -name "$FILENAME" | head -1)" "$DEST_FOLDER/$FILENAME"
  HTTPD_DATADOG_VERSION="$(jq -r '.commit_sha' cpp-httpd-github-actions-artifact.json | cut -c1-12)"
else
  if [ -f cpp-httpd-load-from-release ]; then
    HTTPD_DATADOG_VERSION=$(cat cpp-httpd-load-from-release)
  else
    HTTPD_DATADOG_VERSION="$(get_latest_release DataDog/httpd-datadog)"
  fi
  TARBALL="mod_datadog_artifact.zip"
  URL="https://github.com/DataDog/httpd-datadog/releases/download/${HTTPD_DATADOG_VERSION}/${TARBALL}"
  echo "Get APACHE plugin from $URL"
  curl -Lf -o "$TARBALL" "$URL"
  unzip "$TARBALL" -d "$DEST_FOLDER"
  rm "$TARBALL"
fi

echo '{"status": "ok", "library": {"name": "cpp_httpd", "version": "'"$HTTPD_DATADOG_VERSION"'"}}' > /app/healthcheck.json
echo "$HTTPD_DATADOG_VERSION" > SYSTEM_TESTS_LIBRARY_VERSION
cat /app/healthcheck.json
