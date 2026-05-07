FROM ubuntu:24.04

ARG PHP_VERSION

ADD . /tmp/php

RUN chmod +x /tmp/php/php-fpm/build.sh
RUN /tmp/php/php-fpm/build.sh $PHP_VERSION
RUN rm -rf /tmp/php/
