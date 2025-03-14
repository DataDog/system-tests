#!/bin/bash

set -euv

# Prefix to match
PREFIX="github.com/DataDog/dd-trace-go"

if [ -e "/binaries/dd-trace-go" ]; then
    echo "Install from folder /binaries/dd-trace-go"
    for module in $(go list -m all | awk '{print $1}'); do
      if [[ $module == $PREFIX* ]]; then
        replace_path=${module#"$PREFIX"}
        suffix="/v2"
        replace_path=${replace_path%"$suffix"}
        go mod edit -replace $module=/binaries/dd-trace-go$replace_path
      fi
    done

elif [ -f "/binaries/golang-load-from-go-get" ]; then
    echo "Install from go get -d $(cat /binaries/golang-load-from-go-get)"
    go get -v -d "$(cat /binaries/golang-load-from-go-get)"
    # Pin that version with a `replace` directive so nothing else can override it.
    while IFS=$'\n' read -r line || [ -n "$line" ]; do
        # Extract module path and version by splitting at '@'
        module_path="${line%%@*}"
        # Run go mod edit replace for each module
        go mod edit -replace "$module_path=$line"
    done < /binaries/golang-load-from-go-get
else
    echo "Installing production dd-trace-version"
    # TODO(darccio): remove @$ref on v2 release
    for module in $(go list -m all | awk '{print $1}'); do
      if [[ $module == $PREFIX* ]]; then
        go mod edit -replace $module=$module@v2.0.0-rc.3
      fi
    done
fi

# Downloading a newer version of the tracer may require to resolve again all dependencies
go mod tidy

# Read the library version out of the version.go file
lib_mod_dir=$(go list -f '{{.Dir}}' -m github.com/DataDog/dd-trace-go/v2)
version=$(sed -nrE 's#.*"v(.*)".*#\1#p' "${lib_mod_dir}/internal/version/version.go") # Parse the version string content "v.*"
echo "${version}" > SYSTEM_TESTS_LIBRARY_VERSION

# Output the version of dd-trace-go (per go.mod, as well as the built-in tag).
echo "dd-trace-go go.mod version: $(go list -f '{{ .Version }}' -m github.com/DataDog/dd-trace-go/v2)"
echo "dd-trace-go tag:            ${version}"
