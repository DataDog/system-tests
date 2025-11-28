ARG BASE_IMAGE=ubuntu:24.04
FROM ${BASE_IMAGE} AS app_base
LABEL org.opencontainers.image.source=https://github.com/DataDog/guardrails-testing
USER root
WORKDIR /workdir

COPY base/install_os_deps.sh ./
COPY base/healthcheck.sh /
COPY base/tested_components.sh /

RUN ./install_os_deps.sh ${TARGETPLATFORM}
