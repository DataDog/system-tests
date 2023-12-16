#!/bin/bash

set -eu

if [ "$ENV_LIBRARY_HASH" != "" ]; then
   echo "trying to update $ENV_LIBRARY_HASH"
   go get -u gopkg.in/DataDog/dd-trace-go.v1@"$LIBRARY_HASH"
   go mod tidy
fi
# Read the library version out of the version.go file
mod_dir=$(go list -f '{{.Dir}}' -m gopkg.in/DataDog/dd-trace-go.v1)
version=$(sed -nrE 's#.*"v(.*)".*#\1#p' "$mod_dir"/internal/version/version.go) # Parse the version string content "v.*"
hash=$( cat ./go.mod | grep -e "gopkg.in/DataDog/dd-trace-go.v1 v1.39.0")
echo "$version" > SYSTEM_TESTS_LIBRARY_VERSION
echo "," >> SYSTEM_TESTS_LIBRARY_VERSION
echo "$hash" >> SYSTEM_TESTS_LIBRARY_VERSION