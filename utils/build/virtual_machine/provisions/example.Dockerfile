FROM golang:1.22.1 AS builder
ENV GOBIN=/export/bin
WORKDIR /export

FROM builder AS crane
RUN go install github.com/google/go-containerregistry/cmd/crane@latest
FROM builder AS ecr-login
RUN go install github.com/awslabs/amazon-ecr-credential-helper/ecr-login/cli/docker-credential-ecr-login@latest
RUN set -xe; \
    mkdir -p root/.docker; \
    echo '{"credHelpers":{"669783387624.dkr.ecr.us-east-1.amazonaws.com": "ecr-login"}}' | tee root/.docker/config.json

FROM alpine/curl AS fetcher
RUN set -xe; \
    mkdir -p /tmp/unpack; \
    curl -L -o /tmp/registry.tgz https://github.com/distribution/distribution/releases/download/v2.8.3/registry_2.8.3_linux_amd64.tar.gz; \
    tar -C /tmp/unpack/ -xzf /tmp/registry.tgz; \
    curl -L -o /tmp/unpack/config.yaml https://raw.githubusercontent.com/distribution/distribution-library-image/master/config-example.yml


FROM scratch AS pre-final

COPY --from=fetcher /tmp/unpack/registry /bin/registry
COPY --from=fetcher /tmp/unpack/config.yaml /etc/distribution/config.yml
COPY --from=crane /export /
COPY --from=ecr-login /export /

FROM scratch AS final
COPY --from=pre-final / /