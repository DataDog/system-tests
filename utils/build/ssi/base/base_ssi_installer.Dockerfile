ARG BASE_IMAGE

FROM ${BASE_IMAGE}

WORKDIR /workdir

COPY ./base/install_script_ssi_installer.sh ./

ARG DD_API_KEY=deadbeef
ENV DD_API_KEY=${DD_API_KEY}

RUN ./install_script_ssi_installer.sh

ENV DD_APM_INSTRUMENTATION_DEBUG=true
