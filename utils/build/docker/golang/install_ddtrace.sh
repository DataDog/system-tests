#!/bin/bash

set -eux

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

go mod tidy

# Read the library version out of the version.go file
mod_dir=$(go list -f '{{.Dir}}' -m gopkg.in/DataDog/dd-trace-go.v1)
version=$(sed -nrE 's#.*"v(.*)".*#\1#p' $mod_dir/internal/version/version.go) # Parse the version string content "v.*"
echo $version > /app/SYSTEM_TESTS_LIBRARY_VERSION

touch SYSTEM_TESTS_LIBDDWAF_VERSION

# Read the rule file version
if [[ $version =~ v1.36 ]]; then
    echo "1.2.5" > SYSTEM_TESTS_APPSEC_EVENT_RULES_VERSION
else
    # Parse the appsec rules version string out of the inlined rules json
    rules_version=$(sed -nrE 's#.*rules_version\\\\":\\\\"([[:digit:]\.-]+)\\\\".*#\1#p' $mod_dir/internal/appsec/rule.go)
fi

echo "dd-trace-go version: $(cat /app/SYSTEM_TESTS_LIBRARY_VERSION)"
echo "rules version: $(cat /app/SYSTEM_TESTS_APPSEC_EVENT_RULES_VERSION)"
