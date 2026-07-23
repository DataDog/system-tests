ARG DD_TRACE_C_IMAGE=install.datadoghq.com/apm-library-c-package:latest
ARG AUTO_INJECT_IMAGE=install.datadoghq.com/apm-inject-package:latest

FROM ghcr.io/oras-project/oras:v1.2.3 AS oras

FROM alpine:3.22 AS packages

ARG DD_TRACE_C_IMAGE
ARG AUTO_INJECT_IMAGE
ARG TARGETARCH

COPY --from=oras /bin/oras /usr/local/bin/oras

RUN apk add --no-cache jq zstd \
    && pull_package() { \
        reference="$1"; \
        output="$2"; \
        manifest="$(oras manifest fetch --platform "linux/${TARGETARCH}" "$reference")"; \
        digest="$(printf '%s' "$manifest" | jq -er '.layers[0].digest')"; \
        repository="${reference%:*}"; \
        mkdir -p "$output"; \
        oras blob fetch --output /tmp/package.tar.zst "${repository}@${digest}"; \
        zstd --decompress --stdout /tmp/package.tar.zst | tar -x -C "$output"; \
    }; \
    pull_package "$DD_TRACE_C_IMAGE" /packages/c; \
    pull_package "$AUTO_INJECT_IMAGE" /packages/inject-content; \
    injector_version="$(cat /packages/inject-content/version)"; \
    mkdir -p "/packages/inject/${injector_version}"; \
    cp -a /packages/inject-content/. "/packages/inject/${injector_version}/"; \
    ln -s "$injector_version" /packages/inject/stable

FROM python:3.12-slim

RUN apt-get update \
    && apt-get install --yes --no-install-recommends ca-certificates curl \
    && rm -rf /var/lib/apt/lists/*

COPY --from=packages /packages/c/ /opt/datadog/apm/library/c/
COPY --from=packages /packages/inject/ /opt/datadog-packages/datadog-apm-inject/

WORKDIR /app
COPY utils/build/docker/c/python-stdlib/ /app/

ENV DD_INJECT_FORCE=true
ENV DD_INJECT_NATIVE=always
ENV DD_TRACE_HOOK_MODULES=socket
ENV DD_TRACE_128_BIT_TRACEID_GENERATION_ENABLED=true

EXPOSE 7777
CMD ["./app.sh"]
