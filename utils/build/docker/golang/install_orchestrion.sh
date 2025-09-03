#!/bin/sh

set -eu

if [ -e "/binaries/orchestrion" ]; then
    echo "Install from folder /binaries/orchestrion"
    go mod edit "$(go -C /binaries/orchestrion list -m -f '-replace={{.Path}}={{.Dir}}')"
    go -C /binaries/orchestrion build -o "$(go env GOPATH)/bin/orchestrion" .
elif [ -e "/binaries/orchestrion-load-from-go-get" ]; then
    echo "Install from go get -d $(cat /binaries/orchestrion-load-from-go-get)"
    go get "$(cat /binaries/orchestrion-load-from-go-get)"
    go install "$(cat /binaries/orchestrion-load-from-go-get)"
else
    echo "Installing production orchestrion"
    go get github.com/DataDog/orchestrion@latest
    go install github.com/DataDog/orchestrion@latest
fi

output="$(orchestrion version)"
version="${output#"orchestrion "}"
echo "$version" > /app/SYSTEM_TESTS_ORCHESTRION_VERSION

echo "orchestrion version: $(cat /app/SYSTEM_TESTS_ORCHESTRION_VERSION)"
