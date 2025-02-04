#!/bin/bash

if ldd --version &>/dev/null; then
    # check if is glibc o musl
    if ldd --version | grep -i "musl" &>/dev/null; then
        # if musl
        libc_version=$(musl-gcc -v 2>&1 | grep "musl" | head -n 1 | awk '{print $1 " " $2}')
        export GLIBC_TYPE="musl"
        export GLIBC_VERSION="$libc_version"
    else
        # if glibc
        libc_version=$(ldd --version | head -n 1 | awk '{print $NF}')
        export GLIBC_TYPE="gnu"
        export GLIBC_VERSION="$libc_version"
    fi
else
    echo "The standard C library cannot be determined."
    exit 1
fi