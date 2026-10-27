FROM php:8.2.30-cli-bookworm

# ext-grpc is required by open-telemetry/transport-grpc (OTLP over gRPC is tested).
# It is not packaged for the official image, so it is compiled here once, in the
# prebuilt base image, instead of on every parametric build.
RUN set -eux; \
    apt-get update; \
    apt-get install -y --no-install-recommends $PHPIZE_DEPS zlib1g-dev; \
    MAKEFLAGS="-j$(nproc)" pecl install grpc-1.83.1; \
    docker-php-ext-enable grpc; \
    apt-get purge -y --auto-remove $PHPIZE_DEPS zlib1g-dev; \
    rm -rf /var/lib/apt/lists/* /tmp/pear

COPY --from=composer:2 /usr/bin/composer /usr/local/bin/composer

# install_ddtrace.sh starts with `cd /var/www/html`
RUN mkdir -p /var/www/html

WORKDIR /binaries
COPY parametric/composer.json /binaries/composer.json
COPY parametric/composer.lock /binaries/composer.lock
RUN set -eux; \
    apt-get update; \
    apt-get install -y --no-install-recommends git unzip; \
    composer install --no-interaction --no-progress; \
    composer clear-cache; \
    apt-get purge -y --auto-remove git unzip; \
    rm -rf /var/lib/apt/lists/*
