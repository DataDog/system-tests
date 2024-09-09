ARG BASE_IMAGE

FROM ${BASE_IMAGE}

WORKDIR /workdir

COPY ./base/install_script_ssi.sh ./

ARG DD_API_KEY=deadbeef
ENV DD_API_KEY=${DD_API_KEY}

ARG DD_LANG
ENV DD_APM_INSTRUMENTATION_LIBRARIES=${DD_LANG}

# Disable the injector until we run the application, because it can cause flakyness
#ENV DD_INSTRUMENT_SERVICE_WITH_APM=false
RUN ./install_script_ssi.sh

ENV DD_APM_INSTRUMENTATION_DEBUG=true
ENV DD_INSTRUMENT_SERVICE_WITH_APM=true