#!/bin/bash

if ldd --version &>/dev/null; then

    libc_version=$(ldd --version | head -n 1)
    
    if ldd --version | grep -i "musl" &>/dev/null; then
        export GLIBC_TYPE="musl"
    else
        export GLIBC_TYPE="glibc"
    fi
    
    export GLIBC_VERSION="$libc_version"
else
    echo "The standard C library cannot be determined."
    exit 1
fi
