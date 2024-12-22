#!/bin/bash

set -euv

if [ -e "/binaries/dd-trace-go" ]; then
    echo "Install from folder /binaries/dd-trace-go"
    go mod edit -replace github.com/DataDog/dd-trace-go/v2=/binaries/dd-trace-go
    go mod edit -replace github.com/DataDog/dd-trace-go/contrib/IBM/sarama/v2=/binaries/dd-trace-go/contrib/IBM/sarama
    go mod edit -replace github.com/DataDog/dd-trace-go/contrib/gin-gonic/gin/v2=/binaries/dd-trace-go/contrib/gin-gonic/gin
    go mod edit -replace github.com/DataDog/dd-trace-go/contrib/go-chi/chi.v5/v2=/binaries/dd-trace-go/contrib/go-chi/chi.v5
    go mod edit -replace github.com/DataDog/dd-trace-go/contrib/google.golang.org/grpc/v2=/binaries/dd-trace-go/contrib/google.golang.org/grpc
    go mod edit -replace github.com/DataDog/dd-trace-go/contrib/labstack/echo.v4/v2=/binaries/dd-trace-go/contrib/labstack/echo.v4
    go mod edit -replace github.com/DataDog/dd-trace-go/contrib/net/http/v2=/binaries/dd-trace-go/contrib/net/http

elif [ -e "/binaries/golang-load-from-go-get" ]; then
    echo "Install from go get -d $(cat /binaries/golang-load-from-go-get)"
    cat /binaries/golang-load-from-go-get | xargs go get -v -d

else
    echo "Installing production dd-trace-version"
    # TODO(darccio): remove @$ref on v2 release
    go get -v -d -u github.com/DataDog/dd-trace-go/v2@v2-dev
    go get -v -d -u github.com/DataDog/dd-trace-go/contrib/IBM/sarama/v2@v2-dev
    go get -v -d -u github.com/DataDog/dd-trace-go/contrib/gin-gonic/gin/v2@v2-dev
    go get -v -d -u github.com/DataDog/dd-trace-go/contrib/go-chi/chi.v5/v2@v2-dev
    go get -v -d -u github.com/DataDog/dd-trace-go/contrib/google.golang.org/grpc/v2@v2-dev
    go get -v -d -u github.com/DataDog/dd-trace-go/contrib/labstack/echo.v4/v2@v2-dev
    go get -v -d -u github.com/DataDog/dd-trace-go/contrib/net/http/v2@v2-dev
fi

# Downloading a newer version of the tracer may require to resolve again all dependencies
go mod tidy

# Read the library version out of the version.go file
lib_mod_dir=$(go list -f '{{.Dir}}' -m github.com/DataDog/dd-trace-go/v2)
version=$(sed -nrE 's#.*"v(.*)".*#\1#p' $lib_mod_dir/internal/version/version.go) # Parse the version string content "v.*"
echo $version > SYSTEM_TESTS_LIBRARY_VERSION

rules_mod_dir=$(go list -f '{{.Dir}}' -m github.com/DataDog/appsec-internal-go)


echo "dd-trace-go version: $(cat /app/SYSTEM_TESTS_LIBRARY_VERSION)"
