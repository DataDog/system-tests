ARG PHP_VERSION=8.0
ARG VARIANT=release-zts
ARG APM_LIBRARY_IMAGE=apm_library_latest

FROM ghcr.io/datadog/dd-trace-php/dd-trace-php:latest as apm_library_latest

FROM bash as apm_library_local

ADD binaries* /
RUN touch /LIBRARY_VERSION
RUN touch /LIBDDWAF_VERSION
RUN touch /APPSEC_EVENT_RULES_VERSION
RUN touch /PHP_APPSEC_VERSION

FROM $APM_LIBRARY_IMAGE as apm_library

FROM datadog/dd-appsec-php-ci:php-$PHP_VERSION-$VARIANT

ENV DD_TRACE_ENABLED=1
ENV DD_TRACE_GENERATE_ROOT_SPAN=1
ENV DD_TRACE_AGENT_FLUSH_AFTER_N_REQUESTS=0
ENV DD_TRACE_HEADER_TAGS=user-agent

EXPOSE 7777/tcp

COPY --from=apm_library /LIBRARY_VERSION /binaries/SYSTEM_TESTS_LIBRARY_VERSION
COPY --from=apm_library /LIBDDWAF_VERSION /binaries/SYSTEM_TESTS_LIBDDWAF_VERSION
COPY --from=apm_library /APPSEC_EVENT_RULES_VERSION /binaries/SYSTEM_TESTS_APPSEC_EVENT_RULES_VERSION
COPY --from=apm_library /PHP_APPSEC_VERSION /binaries/SYSTEM_TESTS_PHP_APPSEC_VERSION

COPY --from=apm_library /*.tar.gz /binaries/

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
