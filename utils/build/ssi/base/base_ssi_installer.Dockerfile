ARG BASE_IMAGE

FROM ${BASE_IMAGE}

WORKDIR /workdir

COPY ./base/install_script_ssi_installer.sh ./base/binaries/install_script_agent7.sh ./

ARG DD_API_KEY=deadbeef

RUN ./install_script_ssi_installer.sh
