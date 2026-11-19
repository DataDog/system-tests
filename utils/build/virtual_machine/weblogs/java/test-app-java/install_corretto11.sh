#!/bin/sh
# Fallback JDK 11 install for distros whose package mirrors are not usable from the test VMs
# (EOL Ubuntu repositories returning 404, Fedora mirrors timing out), or whose packaged
# JDK 11 is too old for profiling (see select_java11.sh).
# Installs the official Amazon Corretto 11 tarball, verified against its published sha256.
set -eu

case "$(uname -m)" in
    x86_64) arch=x64 ;;
    aarch64 | arm64) arch=aarch64 ;;
    *)
        echo "Unsupported architecture: $(uname -m)" >&2
        exit 1
        ;;
esac

base_url="https://corretto.aws/downloads"
file="amazon-corretto-11-${arch}-linux-jdk.tar.gz"
# select_java11.sh looks for /usr/lib/jvm/java-11-amazon-corretto.*
target="/usr/lib/jvm/java-11-amazon-corretto.tarball"

download_dir=$(mktemp -d /var/tmp/corretto11.XXXXXX)
trap 'rm -rf "$download_dir"' EXIT

fetch() {
    if command -v curl >/dev/null 2>&1; then
        curl -fsSL --retry 5 --retry-delay 5 --connect-timeout 20 -o "$2" "$1"
    else
        wget -q --tries=5 --timeout=30 -O "$2" "$1"
    fi
}

echo "Downloading Amazon Corretto 11 ($arch)"
fetch "$base_url/latest/$file" "$download_dir/$file"
fetch "$base_url/latest_sha256/$file" "$download_dir/$file.sha256"

expected=$(tr -d ' \n\r' <"$download_dir/$file.sha256")
actual=$(sha256sum "$download_dir/$file" | cut -d ' ' -f 1)
if [ "$expected" != "$actual" ]; then
    echo "Corretto 11 checksum mismatch: expected $expected, got $actual" >&2
    exit 1
fi

sudo rm -rf "$target"
sudo mkdir -p "$target"
sudo tar -xzf "$download_dir/$file" -C "$target" --strip-components=1

echo "Installed Corretto 11 in $target"
"$target/bin/javac" -version
