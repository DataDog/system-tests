#!/usr/bin/env bash

load_base_image() {
    local f="binaries/${TEST_LIBRARY:-}-${WEBLOG_VARIANT:-}-base-image.tar.zst"
    if [ -f "$f" ]; then
        echo "Loading base image from $f"
        zstd -d -c "$f" | docker load
    fi
}
