
FROM ubuntu:24.04
ARG PHP_VERSION=7.3

ADD utils/build/docker/php /tmp/php

RUN chmod +x /tmp/php/php-fpm/build.sh
RUN /tmp/php/php-fpm/build.sh $PHP_VERSION
RUN rm -rf /tmp/php/

# docker build --progress=plain -f utils/build/docker/php/php-fpm-7.3.base.Dockerfile -t datadog/system-tests:php-fpm-7.3.base-v1 .
# docker push datadog/system-tests:php-fpm-7.3.base-v1
