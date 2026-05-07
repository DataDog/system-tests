
FROM datadog/system-tests:php-fpm-8.0.base-v1

ARG PHP_VERSION=8.0

ADD binaries* /binaries/
ADD utils/build/docker/php/common/install_ddtrace.sh /

ENV DD_TRACE_ENABLED=1
ENV DD_TRACE_GENERATE_ROOT_SPAN=1
ENV DD_TRACE_AGENT_FLUSH_AFTER_N_REQUESTS=0
ENV DD_TRACE_HEADER_TAGS=user-agent

RUN /install_ddtrace.sh 0
RUN rm -rf /etc/php/$PHP_VERSION/fpm/conf.d/98-ddappsec.ini

RUN SYSTEM_TESTS_LIBRARY_VERSION=$(cat /binaries/SYSTEM_TESTS_LIBRARY_VERSION) && \
    echo "datadog.trace.request_init_hook = /opt/datadog/dd-library/$SYSTEM_TESTS_LIBRARY_VERSION/dd-trace-sources/bridge/dd_wrap_autoloader.php" >> /etc/php/$PHP_VERSION/fpm/php.ini && \
    echo "datadog.trace.sources_path = /opt/datadog/dd-library/$SYSTEM_TESTS_LIBRARY_VERSION/dd-trace-sources/src" >> /etc/php/$PHP_VERSION/fpm/php.ini

EXPOSE 7777/tcp

WORKDIR /binaries
ENTRYPOINT []
RUN echo "#!/bin/bash\ndumb-init /entrypoint.sh" > app.sh
RUN chmod +x app.sh
CMD [ "./app.sh" ]
