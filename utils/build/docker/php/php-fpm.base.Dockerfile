FROM ubuntu:24.04

ARG PHP_VERSION
ENV PHP_VERSION=${PHP_VERSION}

ADD . /tmp/php

RUN chmod +x /tmp/php/php-fpm/build.sh
RUN /tmp/php/php-fpm/build.sh $PHP_VERSION
RUN rm -rf /tmp/php/

ENV DD_TRACE_ENABLED=1
ENV DD_TRACE_GENERATE_ROOT_SPAN=1
ENV DD_TRACE_AGENT_FLUSH_AFTER_N_REQUESTS=0
ENV DD_TRACE_HEADER_TAGS=user-agent

EXPOSE 7777/tcp
WORKDIR /binaries
ENTRYPOINT []
CMD [ "./app.sh" ]

# Onbuild section: runs in the child image build (per-PHP-version Dockerfile).
# Lets the per-version Dockerfile stay a single FROM line, while still re-overlaying
# the latest weblog PHP files and the dd-trace-php install on every child build.
ONBUILD ADD binaries* /binaries/
ONBUILD ADD utils/build/docker/php/common/ /var/www/html/
ONBUILD RUN cp /var/www/html/install_ddtrace.sh /install_ddtrace.sh && \
    /install_ddtrace.sh 0 && \
    rm /install_ddtrace.sh && \
    rm -rf /etc/php/$PHP_VERSION/fpm/conf.d/98-ddappsec.ini && \
    SYSTEM_TESTS_LIBRARY_VERSION=$(cat /binaries/SYSTEM_TESTS_LIBRARY_VERSION) && \
    echo "datadog.trace.request_init_hook = /opt/datadog/dd-library/$SYSTEM_TESTS_LIBRARY_VERSION/dd-trace-sources/bridge/dd_wrap_autoloader.php" >> /etc/php/$PHP_VERSION/fpm/php.ini && \
    echo "datadog.trace.sources_path = /opt/datadog/dd-library/$SYSTEM_TESTS_LIBRARY_VERSION/dd-trace-sources/src" >> /etc/php/$PHP_VERSION/fpm/php.ini
ONBUILD RUN echo "#!/bin/bash\nexec dumb-init /entrypoint.sh" > /binaries/app.sh && chmod +x /binaries/app.sh
