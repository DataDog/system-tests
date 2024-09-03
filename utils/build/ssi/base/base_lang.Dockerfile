ARG BASE_IMAGE
FROM ${BASE_IMAGE}  as app_base
LABEL org.opencontainers.image.source=https://github.com/DataDog/guardrails-testing

WORKDIR /workdir
RUN echo "test"
ARG ARCH
COPY base/install_os_deps.sh ./
RUN ./install_os_deps.sh ${ARCH}

ARG LANG
ARG RUNTIME_VERSIONS=
COPY base/${LANG}_install_runtimes.sh ./
RUN ./${LANG}_install_runtimes.sh ${RUNTIME_VERSIONS}
ENV JAVA_HOME=java