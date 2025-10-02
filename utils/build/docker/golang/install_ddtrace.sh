#!/bin/bash

set -euv

# Run go mod tidy once to make sure go list does not fail
go mod tidy

MAIN_MODULE="github.com/DataDog/dd-trace-go/v2"
CONTRIBS="$(go list -m all | grep github.com/DataDog/dd-trace-go/contrib | cut -f1 -d' ')"

if [ -e "/binaries/dd-trace-go" ]; then
    echo "Install from folder /binaries/dd-trace-go"
    go mod edit -replace "$MAIN_MODULE=/binaries/dd-trace-go"
    for contrib in $CONTRIBS; do
        path="${contrib#github.com/DataDog/dd-trace-go/}"
        path="${path%/v2}"
        echo "Install contrib $contrib from folder /binaries/dd-trace-go/$path"
        go mod edit -replace "github.com/DataDog/dd-trace-go/$path/v2=/binaries/dd-trace-go/$path"
    done
elif [ -e "/binaries/golang-load-from-go-get" ]; then
    echo "Install from go get"
    # Read the file into an array to ensure we capture all lines
    mapfile -t lines < /binaries/golang-load-from-go-get

    for line in "${lines[@]}"; do
        path="${line%@*}"
        commit="${line#*@}"
        # Get the correct pseudo-version using go list
        pseudo_version=$(go list -m -json "$path@$commit" | jq -r .Version)
        go mod edit -replace "$path=$path@$pseudo_version"
        for contrib in $CONTRIBS; do
            echo "Install contrib $contrib from go get -v $contrib@commit"
            go mod edit -replace "$contrib=$contrib@$pseudo_version"
        done
	break
    done
else
    echo "Installing production dd-trace-version"
    echo "Install from go get -v $MAIN_MODULE@latest"
    version=$(go list -m -json "$MAIN_MODULE@latest" | jq -r .Version)
    go mod edit -replace "$MAIN_MODULE=$MAIN_MODULE@$version"
    for contrib in $CONTRIBS; do
        echo "Install contrib $contrib from go get -v $contrib@latest"
        version=$(go list -m -json "$contrib@latest" | jq -r .Version)
        go mod edit -replace "$contrib=$contrib@$version"
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
