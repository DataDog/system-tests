#!/bin/sh

set -e

GO_VERSION=go1.22.0

case "$(uname -m)" in
arm64|aarch64) GO_ARCH=arm64;;
amd64|x86_64) GO_ARCH=amd64;;
*)
        echo "unrecognized architecture $(uname -m)"
        exit 1
        ;;
esac

if command -v apt; then
        apt update -y
        apt install -y curl
else
        yum install -y curl
fi

# install go
GO_TAR="${GO_VERSION}.linux-${GO_ARCH}.tar.gz"
curl -O -L "https://go.dev/dl/${GO_TAR}"
tar -C /usr/local -xzf ${GO_TAR}
export PATH="${PATH}":/usr/local/go/bin

# install orchestrion

ORCHESTRION_VERSION="latest"
if [ "${ONBOARDING_FILTER_ENV}" = "dev" ]; then
        ORCHESTRION_VERSION="main"
fi
go install "github.com/DataDog/orchestrion@${ORCHESTRION_VERSION}"

# build & install test app
mkdir -p /home/datadog/build
cp main.go /home/datadog/build
cd /home/datadog/build
go mod init test-app-go
"${HOME}"/go/bin/orchestrion go build -o /home/datadog/test-app-go