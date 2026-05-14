ARG PHP_VERSION=8.2
ARG VARIANT=release

FROM datadog/dd-appsec-php-ci:php-$PHP_VERSION-$VARIANT

ENV DD_TRACE_ENABLED=1
ENV DD_TRACE_GENERATE_ROOT_SPAN=1
ENV DD_TRACE_AGENT_FLUSH_AFTER_N_REQUESTS=0
ENV DD_TRACE_HEADER_TAGS=user-agent

EXPOSE 7777/tcp

ADD binaries* /binaries/
ADD utils/build/docker/php /tmp/php

# Use Laravel-specific Apache config (DocumentRoot public/, AllowOverride All)
RUN cp /tmp/php/weblogs/laravel11x/.apache.conf /tmp/php/apache-mod/php.conf

# Pre-create .env with APP_KEY and file-based session (no DB needed)
RUN mkdir -p /var/www/html && \
    php -r "echo 'APP_KEY=base64:' . base64_encode(random_bytes(32)) . PHP_EOL;" > /var/www/html/.env && \
    echo "SESSION_DRIVER=file" >> /var/www/html/.env && \
    echo "APP_DEBUG=true" >> /var/www/html/.env

RUN chmod +x /tmp/php/apache-mod/build.sh
RUN /tmp/php/apache-mod/build.sh laravel11x
RUN touch /tmp/laravel.db && \
    cd /var/www/html && \
    php artisan migrate --force --no-interaction && \
    php artisan db:seed --force --no-interaction && \
    chmod 666 /tmp/laravel.db

# Install ddtrace (same pattern as apache-mod-X.Y.Dockerfiles)
ADD utils/build/docker/php/common/install_ddtrace.sh /install_ddtrace.sh
RUN /install_ddtrace.sh 1

# Set writable permissions on storage, and create the log dir expected by the entrypoint
RUN mkdir -p /var/log/system-tests && \
    chmod -R 775 /var/www/html/storage /var/www/html/bootstrap/cache && \
    chown -R www-data:www-data /var/www/html/storage /var/www/html/bootstrap/cache

RUN rm -rf /tmp/php/

ADD utils/build/docker/php/apache-mod/entrypoint.sh /
WORKDIR /binaries
ENTRYPOINT []
RUN echo "#!/bin/bash\ndumb-init /entrypoint.sh" > app.sh
RUN chmod +x app.sh
CMD [ "./app.sh" ]
