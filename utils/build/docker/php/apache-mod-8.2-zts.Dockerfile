ARG TRACER_IMAGE=agent_local
ARG PHP_VERSION=8.2
ARG VARIANT=release-zts

#TODO RMM: The images will be in dd-trace-java repository. Now for tests purposes we are using system-tests repository
FROM ghcr.io/datadog/system-tests/dd-trace-php:latest_snapshot as agent_latest_snapshot

FROM ghcr.io/datadog/system-tests/dd-trace-php:latest as agent_latest

FROM bash as agent_local

ADD binaries* /binaries/
RUN touch /LIBRARY_VERSION
RUN touch /LIBDDWAF_VERSION
RUN touch /APPSEC_EVENT_RULES_VERSION
RUN touch /PHP_APPSEC_VERSION

FROM $TRACER_IMAGE as agent

FROM datadog/dd-appsec-php-ci:php-$PHP_VERSION-$VARIANT

ENV DD_TRACE_ENABLED=1
ENV DD_TRACE_GENERATE_ROOT_SPAN=1
ENV DD_TRACE_AGENT_FLUSH_AFTER_N_REQUESTS=0
ENV DD_TRACE_HEADER_TAGS=user-agent

EXPOSE 7777/tcp

COPY --from=agent /LIBRARY_VERSION /binaries/SYSTEM_TESTS_LIBRARY_VERSION
COPY --from=agent /LIBDDWAF_VERSION /binaries/SYSTEM_TESTS_LIBDDWAF_VERSION
COPY --from=agent /APPSEC_EVENT_RULES_VERSION /binaries/SYSTEM_TESTS_APPSEC_EVENT_RULES_VERSION
COPY --from=agent /PHP_APPSEC_VERSION /binaries/SYSTEM_TESTS_PHP_APPSEC_VERSION

COPY --from=agent /*.tar.gz /binaries/

ADD utils/build/docker/php /tmp/php

RUN chmod +x /tmp/php/apache-mod/build.sh
RUN /tmp/php/apache-mod/build.sh
RUN rm -rf /tmp/php/

ADD utils/build/docker/php/apache-mod/entrypoint.sh /
WORKDIR /binaries
ENTRYPOINT []
RUN echo "#!/bin/bash\ndumb-init /entrypoint.sh" > app.sh
RUN chmod +x app.sh
CMD [ "./app.sh" ]
