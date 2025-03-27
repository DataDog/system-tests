#!/bin/bash
set -eu

get_latest_release() {
    curl "https://api.github.com/repos/$1/releases/latest" | jq -r '.tag_name'
}

FILENAME=mod_datadog.so
DEST_FOLDER=/usr/lib/apache2/modules

cd /binaries

if [ -f "$FILENAME" ]; then
  echo "Install HTTPD plugin from binaries/$FILENAME"
  HTTPD_DATADOG_VERSION="v99.99.99"  # TODO: get version from the binary. Right now, use the "big-version" trick
  cp $FILENAME "$DEST_FOLDER/$FILENAME"
else
  HTTPD_DATADOG_VERSION="$(get_latest_release DataDog/httpd-datadog)"
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

