FROM ubuntu:24.04

ARG PHP_VERSION
ENV PHP_VERSION=${PHP_VERSION}

# build.sh only reads from these four subdirectories (see php-fpm/build.sh); keep this
# list in sync with it, since it drives the base-image content hash.
COPY apt-sources.d /tmp/php/apt-sources.d
COPY weblogs /tmp/php/weblogs
COPY php-fpm /tmp/php/php-fpm
COPY common /tmp/php/common

RUN chmod +x /tmp/php/php-fpm/build.sh
RUN /tmp/php/php-fpm/build.sh $PHP_VERSION
RUN rm -rf /tmp/php/

ENV DD_TRACE_ENABLED=1
ENV DD_TRACE_GENERATE_ROOT_SPAN=1
ENV DD_TRACE_AGENT_FLUSH_AFTER_N_REQUESTS=0
ENV DD_TRACE_HEADER_TAGS=user-agent

# docker build --progress=plain --build-arg PHP_VERSION=8.2 -f utils/build/docker/php/php-fpm.base.Dockerfile -t datadog/system-tests:php-fpm-8.2.base utils/build/docker/php
# docker push datadog/system-tests:php-fpm-8.2.base
