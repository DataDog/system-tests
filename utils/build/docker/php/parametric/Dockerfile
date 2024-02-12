
FROM datadog/dd-trace-ci:php-8.2_buster
WORKDIR /binaries
ENV DD_TRACE_CLI_ENABLED=1
ADD utils/build/docker/php/parametric/composer.json .
ADD utils/build/docker/php/parametric/composer.lock .
RUN composer install
ADD utils/build/docker/php/parametric/../common/install_ddtrace.sh .
COPY binaries /binaries
RUN NO_EXTRACT_VERSION=Y ./install_ddtrace.sh
ADD utils/build/docker/php/parametric/server.php .
