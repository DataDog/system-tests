ARG BASE_IMAGE
FROM ${BASE_IMAGE}  as app_base
LABEL org.opencontainers.image.source=https://github.com/DataDog/guardrails-testing
USER root
WORKDIR /workdir
ARG ARCH
COPY base/install_os_deps.sh ./
COPY base/healthcheck.sh /
COPY base/tested_components.sh /

RUN ./install_os_deps.sh ${ARCH}
