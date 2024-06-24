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

# Downloading a newer version of the tracer may require to resolve again all dependencies
go mod tidy

# Read the library version out of the version.go file
lib_mod_dir=$(go list -f '{{.Dir}}' -m gopkg.in/DataDog/dd-trace-go.v1)
version=$(sed -nrE 's#.*"v(.*)".*#\1#p' $lib_mod_dir/internal/version/version.go) # Parse the version string content "v.*"
echo $version >SYSTEM_TESTS_LIBRARY_VERSION

touch SYSTEM_TESTS_LIBDDWAF_VERSION

rules_mod_dir=$(go list -f '{{.Dir}}' -m github.com/DataDog/appsec-internal-go)

# Read the rule file version
if [[ -f $lib_mod_dir/internal/appsec/rules.json ]]; then
    # Look for the ruleset in dd-trace-go
    rules_version=$(jq -r .metadata.rules_version $lib_mod_dir/internal/appsec/rules.json)
elif [[ -f $rules_mod_dir/appsec/rules.json ]]; then
    # Look for the ruleset in appsec-internal-go
    rules_version=$(jq -r .metadata.rules_version $rules_mod_dir/appsec/rules.json)
elif [[ $(cat $rules_mod_dir/appsec/rules.go) =~ rules_version\\\":\\\"([[:digit:].-]+)\\\" ]]; then
    # Parse the appsec rules version string out of the inlined rules json
    rules_version="${BASH_REMATCH[1]}"
else
    rules_version="1.2.5"
fi
echo $rules_version >SYSTEM_TESTS_APPSEC_EVENT_RULES_VERSION

echo "dd-trace-go version: $(cat /app/SYSTEM_TESTS_LIBRARY_VERSION)"
echo "rules version: $(cat /app/SYSTEM_TESTS_APPSEC_EVENT_RULES_VERSION)"
