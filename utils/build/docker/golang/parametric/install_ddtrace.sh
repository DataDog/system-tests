#!/bin/bash

set -euv

# Downloading a newer version of the tracer may require to resolve again all dependencies
go mod tidy

# Read the library version out of the version.go file
lib_mod_dir=$(go list -f '{{.Dir}}' -m gopkg.in/DataDog/dd-trace-go.v1)
version=$(sed -nrE 's#.*"v(.*)".*#\1#p' "$lib_mod_dir"/internal/version/version.go) # Parse the version string content "v.*"
echo "$version" > SYSTEM_TESTS_LIBRARY_VERSION


echo "dd-trace-go version: $(cat /app/SYSTEM_TESTS_LIBRARY_VERSION)"