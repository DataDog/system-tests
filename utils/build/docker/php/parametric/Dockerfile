# Official php image + ext-grpc + composer dependencies, see utils/build/docker/php/parametric.base.Dockerfile
FROM system_tests_base_php_php_parametric
WORKDIR /binaries
ENV DD_TRACE_CLI_ENABLED=1
COPY utils/build/docker/php/common/install_ddtrace.sh .
COPY binaries /binaries
RUN NO_EXTRACT_VERSION=Y ./install_ddtrace.sh
RUN php -d error_reporting='' -r 'echo phpversion("ddtrace");' > SYSTEM_TESTS_LIBRARY_VERSION
ENV OTEL_PHP_AUTOLOAD_ENABLED=true
COPY utils/build/docker/php/parametric/server.php .

 # In case of crash, give time to the sidecar to upload the crash report
CMD ["bash", "-c", "php server.php ${SYSTEM_TESTS_EXTRA_COMMAND_ARGUMENTS:-} || sleep 2s"]
