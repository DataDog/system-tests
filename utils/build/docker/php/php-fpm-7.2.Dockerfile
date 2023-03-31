ARG APM_LIBRARY_IMAGE=apm_library_latest

FROM ghcr.io/datadog/dd-trace-php/dd-trace-php:latest as apm_library_latest

FROM bash as apm_library_local

ADD binaries* /
RUN touch /LIBRARY_VERSION
RUN touch /LIBDDWAF_VERSION
RUN touch /APPSEC_EVENT_RULES_VERSION
RUN touch /PHP_APPSEC_VERSION

FROM $APM_LIBRARY_IMAGE as apm_library

FROM ubuntu:20.04
ARG PHP_VERSION=7.2

COPY --from=apm_library /LIBRARY_VERSION /binaries/SYSTEM_TESTS_LIBRARY_VERSION
COPY --from=apm_library /LIBDDWAF_VERSION /binaries/SYSTEM_TESTS_LIBDDWAF_VERSION
COPY --from=apm_library /APPSEC_EVENT_RULES_VERSION /binaries/SYSTEM_TESTS_APPSEC_EVENT_RULES_VERSION
COPY --from=apm_library /PHP_APPSEC_VERSION /binaries/SYSTEM_TESTS_PHP_APPSEC_VERSION

COPY --from=apm_library /*.tar.gz /binaries/

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
