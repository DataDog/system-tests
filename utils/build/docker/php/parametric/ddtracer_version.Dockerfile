
FROM datadog/dd-trace-ci:php-8.2_buster
RUN sudo apt-get update
RUN sudo apt-get -y install jq
WORKDIR /binaries
ENV DD_TRACE_CLI_ENABLED=1
ADD ./utils/build/docker/php/parametric/composer.json .
ADD ./utils/build/docker/php/parametric//composer.lock .
ADD ./utils/build/docker/php/parametric//server.php .
ADD ./utils/build/docker/php/common/install_ddtrace.sh .
COPY binaries /binaries

RUN NO_EXTRACT_VERSION=Y ./install_ddtrace.sh
RUN php -d error_reporting='' -r 'echo phpversion("ddtrace");' > SYSTEM_TESTS_LIBRARY_VERSION
CMD cat ./SYSTEM_TESTS_LIBRARY_VERSION