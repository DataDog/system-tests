ARG PHP_VERSION
ARG VARIANT=release
FROM datadog/dd-appsec-php-ci:php-${PHP_VERSION}-${VARIANT}

ENV DD_TRACE_ENABLED=1
ENV DD_TRACE_GENERATE_ROOT_SPAN=1
ENV DD_TRACE_AGENT_FLUSH_AFTER_N_REQUESTS=0
ENV DD_TRACE_HEADER_TAGS=user-agent

EXPOSE 7777/tcp

ADD . /tmp/php
RUN chmod +x /tmp/php/apache-mod/build.sh
RUN /tmp/php/apache-mod/build.sh
RUN rm -rf /tmp/php/

WORKDIR /binaries
ENTRYPOINT []
CMD [ "./app.sh" ]

# Onbuild section: runs in the child image build (per-PHP-version Dockerfile).
# Re-overlays the latest weblog PHP files and runs the dd-trace-php install
# against the freshly added /binaries on every child build.
ONBUILD ADD binaries* /binaries/
ONBUILD ADD utils/build/docker/php/common/ /var/www/html/
ONBUILD ADD utils/build/docker/php/apache-mod/entrypoint.sh /
ONBUILD RUN cp /var/www/html/install_ddtrace.sh /install_ddtrace.sh && \
    /install_ddtrace.sh 1 && \
    rm /install_ddtrace.sh
ONBUILD RUN echo "#!/bin/bash\nexec dumb-init /entrypoint.sh" > /binaries/app.sh && chmod +x /binaries/app.sh
