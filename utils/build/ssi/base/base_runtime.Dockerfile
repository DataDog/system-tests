ARG BASE_IMAGE
FROM ${BASE_IMAGE}  as app_base
LABEL org.opencontainers.image.source=https://github.com/DataDog/guardrails-testing

WORKDIR /workdir

ARG DD_LANG
ARG RUNTIME_VERSIONS=
COPY base/${DD_LANG}_install_runtimes.sh ./
RUN ./${DD_LANG}_install_runtimes.sh ${RUNTIME_VERSIONS}