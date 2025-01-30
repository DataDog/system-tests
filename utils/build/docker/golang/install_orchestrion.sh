#!/bin/bash

set -euv

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

orchestrion pin

output="$(orchestrion version)"
version="${output#"orchestrion "}"
echo "$version" > SYSTEM_TESTS_ORCHESTRION_VERSION

echo "orchestrion version: $(cat /app/SYSTEM_TESTS_ORCHESTRION_VERSION)"
