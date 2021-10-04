#!/bin/bash

set -eu

cd /app

if [ -d "binaries/dd-trace-go" ]; then
    echo "Install from folder binaries/dd-trace-go"
    go mod edit -replace gopkg.in/DataDog/dd-trace-go.v1=$(pwd)/binaries/dd-trace-go

elif [ $(ls binaries/golang-load-from-go-get | wc -l) = 1 ]; then
    echo "Install from got get $(cat binaries/golang-load-from-go-get)"
    go get "$(cat binaries/golang-load-from-go-get)"

else
    echo "Install production version"
    go get gopkg.in/DataDog/dd-trace-go.v1/ddtrace
fi

go build -v .

go list -m all | grep dd-trace-go | sed 's/.* v//' > /app/SYSTEM_TESTS_LIBRARY_VERSION
