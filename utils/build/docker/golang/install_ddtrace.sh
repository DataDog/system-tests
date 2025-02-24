#!/bin/bash

set -euv

if [ -e "/binaries/dd-trace-go" ]; then
    echo "Install from folder /binaries/dd-trace-go"
    go mod edit -replace gopkg.in/DataDog/dd-trace-go.v1=/binaries/dd-trace-go

elif [ -e "/binaries/golang-load-from-go-get" ]; then
    echo "Install from go get -d $(cat /binaries/golang-load-from-go-get)"
    go get -v -d "$(cat /binaries/golang-load-from-go-get)"
    # Pin that version with a `replace` directive so nothing else can override it.
    go mod edit -replace "gopkg.in/DataDog/dd-trace-go.v1=$(cat /binaries/golang-load-from-go-get)"

else
    echo "Installing production dd-trace-version"
    go get -v gopkg.in/DataDog/dd-trace-go.v1@latest
fi

# Downloading a newer version of the tracer may require to resolve again all dependencies
go mod tidy

# Read the library version out of the version.go file
lib_mod_dir=$(go list -f '{{.Dir}}' -m gopkg.in/DataDog/dd-trace-go.v1)
version=$(sed -nrE 's#.*"v(.*)".*#\1#p' "${lib_mod_dir}/internal/version/version.go") # Parse the version string content "v.*"
echo "${version}" > SYSTEM_TESTS_LIBRARY_VERSION

# Output the version of dd-trace-go (per go.mod, as well as the built-in tag).
echo "dd-trace-go go.mod version: $(go list -f '{{ .Version }}' -m gopkg.in/DataDog/dd-trace-go.v1)"
echo "dd-trace-go tag:            ${version}"
