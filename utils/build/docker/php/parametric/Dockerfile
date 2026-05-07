
FROM datadog/dd-trace-ci:php-8.2_bookworm-6
RUN switch-php nts
WORKDIR /binaries
ENV DD_TRACE_CLI_ENABLED=1
# Use individual bridge files (src/bridge/_files_*.php) instead of the bundled
# _generated_*.php, so the PR's per-file overrides in /binaries/src take effect
# without having to regenerate the bundle locally.
ENV DD_AUTOLOAD_NO_COMPILE=true
ADD utils/build/docker/php/parametric/composer.json .
ADD utils/build/docker/php/parametric/composer.lock .
RUN composer install
ADD utils/build/docker/php/parametric/../common/install_ddtrace.sh .
COPY binaries /binaries
RUN NO_EXTRACT_VERSION=Y ./install_ddtrace.sh
RUN DDTRACE_SOURCES=$(find /opt/datadog -type d -name "dd-trace-sources" 2>/dev/null | head -1) && \
    if [ -n "$DDTRACE_SOURCES" ] && [ -d /binaries/src ]; then \
      cp -r /binaries/src/. "$DDTRACE_SOURCES/src/"; \
    fi
RUN php -d error_reporting='' -r 'echo phpversion("ddtrace");' > SYSTEM_TESTS_LIBRARY_VERSION
ADD utils/build/docker/php/parametric/server.php .
# RUN mkdir /parametric-tracer-logs

 # In case of crash, give time to the sidecar to upload the crash report
CMD ["bash", "-c", "php server.php ${SYSTEM_TESTS_EXTRA_COMMAND_ARGUMENTS:-} || sleep 2s"]
