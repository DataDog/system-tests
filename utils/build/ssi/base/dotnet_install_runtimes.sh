#!/bin/bash

export DOTNET_VERSION=$1
set -e

curl -sSL https://dot.net/v1/dotnet-install.sh --output dotnet-install.sh  \
    && chmod +x ./dotnet-install.sh \
    && ./dotnet-install.sh --version $DOTNET_VERSION --install-dir /usr/share/dotnet \
    && rm ./dotnet-install.sh \
    && ln -s /usr/share/dotnet/dotnet /usr/bin/dotnet

for VERSION in $(echo "$RUNTIME_VERSIONS" | tr ',' ' '); do
    sleep $((1 + RANDOM % 10)) # Sleep a random 1-10 seconds to avoid sdkman rate limits
    sdk install java "$VERSION"
done

ln -s "${SDKMAN_DIR}/candidates/java/current/bin/java" /usr/bin/java
ln -s "${SDKMAN_DIR}/candidates/java/current/bin/javac" /usr/bin/javac