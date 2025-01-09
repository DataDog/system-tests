#!/bin/bash

set -euv

if [ -e "/binaries/dd-trace-go" ]; then
    echo "Install from folder /binaries/dd-trace-go"
    go mod edit -replace gopkg.in/DataDog/dd-trace-go.v1=/binaries/dd-trace-go

elif [ -e "/binaries/golang-load-from-go-get" ]; then
    echo "Install from go get -d $(cat /binaries/golang-load-from-go-get)"
    go get -v -d "$(cat /binaries/golang-load-from-go-get)"

else
    echo "Installing production dd-trace-version"
    go get -v -d -u gopkg.in/DataDog/dd-trace-go.v1
fi

# Install orchestrion
if [ -n "$INSTALL_ORCHESTRION" ]; then
    if [ -e "/binaries/orchestrion" ]; then
        echo "Install from folder /binaries/orchestrion"
        go mod edit -replace github.com/DataDog/orchestrion=/binaries/orchestrion
        go -C /binaries/orchestrion build -o "$(go env GOPATH)/bin/orchestrion" .
    elif [ -e "/binaries/orchestrion-load-from-go-get" ]; then
        echo "Install from go get -d $(cat /binaries/orchestrion-load-from-go-get)"
        go install "$(cat /binaries/orchestrion-load-from-go-get)"
    else
        echo "Installing production orchestrion"
        go install github.com/DataDog/orchestrion@latest
    fi
fi


# Downloading a newer version of the tracer may require to resolve again all dependencies
go mod tidy

# Read the library version out of the version.go file
lib_mod_dir=$(go list -f '{{.Dir}}' -m gopkg.in/DataDog/dd-trace-go.v1)
version=$(sed -nrE 's#.*"v(.*)".*#\1#p' $lib_mod_dir/internal/version/version.go) # Parse the version string content "v.*"
echo $version > SYSTEM_TESTS_LIBRARY_VERSION

rules_mod_dir=$(go list -f '{{.Dir}}' -m github.com/DataDog/appsec-internal-go)


echo "dd-trace-go version: $(cat /app/SYSTEM_TESTS_LIBRARY_VERSION)"
