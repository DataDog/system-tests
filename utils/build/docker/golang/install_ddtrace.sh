#!/bin/bash

set -eu

if [ -e "/binaries/dd-trace-go" ]; then
    echo "Install from folder /binaries/dd-trace-go"
    go mod edit -replace gopkg.in/DataDog/dd-trace-go.v1=/binaries/dd-trace-go

elif [ -e "/binaries/golang-load-from-go-get" ]; then
    echo "Install from got get $(cat /binaries/golang-load-from-go-get)"
    go get -d "$(cat /binaries/golang-load-from-go-get)"

else
    echo "Installing production dd-trace-version"
    go get -d gopkg.in/DataDog/dd-trace-go.v1
fi

go mod tidy

go list -m all | grep dd-trace-go | sed 's/.* v//' | sed 's/-.*//' > /app/SYSTEM_TESTS_LIBRARY_VERSION
echo "dd-trace version: $(cat /app/SYSTEM_TESTS_LIBRARY_VERSION)"
