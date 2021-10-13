#!/bin/bash

set -eu

cd /app

if [ -e "/binaries/dd-trace-go" ]; then
    echo "Install from folder /binaries/dd-trace-go"
    go mod edit -replace gopkg.in/DataDog/dd-trace-go.v1=/binaries/dd-trace-go
    go mod tidy

elif [ -e "/binaries/golang-load-from-go-get" ]; then
    echo "Install from got get $(cat /binaries/golang-load-from-go-get)"
    go get "$(cat binaries/golang-load-from-go-get)"

else
    echo "Installing production dd-trace- version"
    go get -d gopkg.in/DataDog/dd-trace-go.v1
fi

go build -tags appsec -v .

go list -m all | grep dd-trace-go | sed 's/.* v//' > /app/SYSTEM_TESTS_LIBRARY_VERSION
