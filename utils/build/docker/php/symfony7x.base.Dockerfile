ARG PHP_VERSION=8.2
ARG VARIANT=release

FROM datadog/dd-appsec-php-ci:php-$PHP_VERSION-$VARIANT

ENV DD_TRACE_ENABLED=1
ENV DD_TRACE_GENERATE_ROOT_SPAN=1
ENV DD_TRACE_AGENT_FLUSH_AFTER_N_REQUESTS=0
ENV DD_TRACE_HEADER_TAGS=user-agent

EXPOSE 7777/tcp

# build.sh installs apache, the PHP extensions, dumb-init and composer, then runs `composer install`.
# Only the composer.json and the Acme path repository of the weblog are copied, so that editing the
# weblog sources does not require a new base image: the weblog Dockerfile adds them, and regenerates
# the autoloader. Keep this list in sync with build.sh, since it drives the base-image content hash.
COPY apache-mod /tmp/php/apache-mod
COPY common /tmp/php/common
COPY weblogs/symfony7x/composer.json /tmp/php/weblogs/symfony7x/composer.json
COPY weblogs/symfony7x/Acme /tmp/php/weblogs/symfony7x/Acme

RUN chmod +x /tmp/php/apache-mod/build.sh
RUN /tmp/php/apache-mod/build.sh symfony7x
RUN rm -rf /tmp/php/
