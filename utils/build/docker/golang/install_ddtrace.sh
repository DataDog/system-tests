#!/bin/bash

set -eux

if [ -e "/binaries/dd-trace-go" ]; then
    echo "Install from folder /binaries/dd-trace-go"
    go mod edit -replace gopkg.in/DataDog/dd-trace-go.v1=/binaries/dd-trace-go
    # Read from the version file directly because go list cannot know the local
    # directory version
    version_file=$(go list -f '{{.Dir}}' -m gopkg.in/DataDog/dd-trace-go.v1)/internal/version/version.go
    # Parse and print the version string content "v.*"
    version=$(sed -nrE 's#.*"v(.*)".*#\1#p' $version_file)

elif [ -e "/binaries/golang-load-from-go-get" ]; then
    echo "Install from go get -d $(cat /binaries/golang-load-from-go-get)"
    go get -v -d "$(cat /binaries/golang-load-from-go-get)"
    version=$(go list -f '{{.Version}}' -m gopkg.in/DataDog/dd-trace-go.v1)

else
    echo "Installing production dd-trace-version"
    go get -v -d -u gopkg.in/DataDog/dd-trace-go.v1
    version=$(go list -f '{{.Version}}' -m gopkg.in/DataDog/dd-trace-go.v1)
fi

go mod tidy

echo $version > /app/SYSTEM_TESTS_LIBRARY_VERSION
touch SYSTEM_TESTS_LIBDDWAF_VERSION
if [[ $version >= "1.37.0" ]]; then
    # Parse the appsec rules version string out of the inlined rules json
    mod_dir=$(go list -f '{{.Dir}}' -m gopkg.in/DataDog/dd-trace-go.v1)
    rules_version=$(sed -nrE 's#.*rules_version\\\\":\\\\"([[:digit:]\.-]+)\\\\".*#\1#p' $mod_dir/internal/appsec/rule.go)
else
    echo "1.2.5" > SYSTEM_TESTS_APPSEC_EVENT_RULES_VERSION
fi

echo "dd-trace-go version: $(cat /app/SYSTEM_TESTS_LIBRARY_VERSION)"
echo "rules version: $(cat /app/SYSTEM_TESTS_APPSEC_EVENT_RULES_VERSION)"
