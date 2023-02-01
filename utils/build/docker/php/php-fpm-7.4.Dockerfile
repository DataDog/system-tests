ARG TRACER_IMAGE=agent_local

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

FROM ubuntu:20.04
ARG PHP_VERSION=7.4

COPY --from=agent /LIBRARY_VERSION /binaries/SYSTEM_TESTS_LIBRARY_VERSION
COPY --from=agent /LIBDDWAF_VERSION /binaries/SYSTEM_TESTS_LIBDDWAF_VERSION
COPY --from=agent /APPSEC_EVENT_RULES_VERSION /binaries/SYSTEM_TESTS_APPSEC_EVENT_RULES_VERSION
COPY --from=agent /PHP_APPSEC_VERSION /binaries/SYSTEM_TESTS_PHP_APPSEC_VERSION

COPY --from=agent /*.tar.gz /binaries/

ADD utils/build/docker/php /tmp/php

ENV DD_TRACE_ENABLED=1
ENV DD_TRACE_GENERATE_ROOT_SPAN=1
ENV DD_TRACE_AGENT_FLUSH_AFTER_N_REQUESTS=0
ENV DD_TRACE_HEADER_TAGS=user-agent

RUN chmod +x /tmp/php/php-fpm/build.sh
RUN /tmp/php/php-fpm/build.sh $PHP_VERSION
RUN rm -rf /tmp/php/

EXPOSE 7777/tcp

WORKDIR /binaries
ENTRYPOINT []
RUN echo "#!/bin/bash\ndumb-init /entrypoint.sh" > app.sh
RUN chmod +x app.sh
CMD [ "./app.sh" ]
