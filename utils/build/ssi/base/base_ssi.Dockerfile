ARG BASE_IMAGE

FROM ${BASE_IMAGE}

WORKDIR /workdir

COPY ./base/install_script_ssi.sh ./

ARG DD_API_KEY=deadbeef

ARG DD_LANG
ENV DD_APM_INSTRUMENTATION_LIBRARIES=${DD_LANG}

ARG SSI_ENV
ENV SSI_ENV=${SSI_ENV}

ARG DD_INSTALLER_LIBRARY_VERSION
ENV DD_INSTALLER_LIBRARY_VERSION=${DD_INSTALLER_LIBRARY_VERSION}

ARG DD_INSTALLER_INJECTOR_VERSION
ENV DD_INSTALLER_INJECTOR_VERSION=${DD_INSTALLER_INJECTOR_VERSION}

RUN ./install_script_ssi.sh

ENV DD_APM_INSTRUMENTATION_DEBUG=true
ENV DD_INSTRUMENT_SERVICE_WITH_APM=true