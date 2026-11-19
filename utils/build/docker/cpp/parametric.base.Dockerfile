ARG TARGETARCH
FROM datadog/docker-library:dd-trace-cpp-ci-23768e9-${TARGETARCH}

# Install build dependencies once so parametric shards do not need the Ubuntu mirror.
RUN apt-get update \
 && apt-get -y install pkg-config libabsl-dev curl jq \
 && rm -rf /var/lib/apt/lists/*
