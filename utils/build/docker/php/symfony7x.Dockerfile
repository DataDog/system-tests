ARG PHP_VERSION=8.2
ARG VARIANT=release

FROM datadog/dd-appsec-php-ci:php-$PHP_VERSION-$VARIANT

ENV PHP_VERSION=8.2
ENV DD_TRACE_ENABLED=1
ENV DD_TRACE_GENERATE_ROOT_SPAN=1
ENV DD_TRACE_AGENT_FLUSH_AFTER_N_REQUESTS=0
ENV DD_TRACE_HEADER_TAGS=user-agent

EXPOSE 7777/tcp

ADD binaries* /binaries/
ADD utils/build/docker/php /tmp/php

# Pre-create .env with APP_SECRET and APP_ENV
RUN mkdir -p /var/www/html && \
    echo "APP_ENV=prod" > /var/www/html/.env && \
    php -r "echo 'APP_SECRET=' . bin2hex(random_bytes(16)) . PHP_EOL;" >> /var/www/html/.env && \
    echo "APP_DEBUG=0" >> /var/www/html/.env && \
    echo "SYMFONY_DB_PATH=/tmp/symfony.db" >> /var/www/html/.env

RUN chmod +x /tmp/php/apache-mod/build.sh
RUN /tmp/php/apache-mod/build.sh symfony7x

# Use Symfony-specific Apache config (DocumentRoot public/, AllowOverride All)
RUN cp /tmp/php/weblogs/symfony7x/.apache.conf /etc/apache2/mods-available/php.conf && \
    sed -i "s/%PHP_MAJOR_VERSION//g" /etc/apache2/mods-available/php.conf && \
    ln -sf /etc/apache2/mods-available/php.conf /etc/apache2/mods-enabled/php.conf

# pdo_sqlite, dom, and tokenizer are needed by Symfony (mirrors laravel11x pattern; tokenizer for attribute routing)
RUN printf "extension=dom.so\nextension=pdo_sqlite.so\nextension=tokenizer.so\n" >> /etc/php/php.ini

# Create log directory before running PHP (php.ini writes error_log there)
RUN mkdir -p /var/log/system-tests

# Create SQLite database and seed test users (script is at /var/www/html/bin/init-db.php via build.sh)
RUN SYMFONY_DB_PATH=/tmp/symfony.db php /var/www/html/bin/init-db.php && \
    chmod 666 /tmp/symfony.db

# Warm up Symfony cache
RUN cd /var/www/html && APP_ENV=prod php bin/console cache:warmup

# Install ddtrace (same pattern as apache-mod-X.Y.Dockerfiles)
ADD utils/build/docker/php/common/install_ddtrace.sh /install_ddtrace.sh
RUN /install_ddtrace.sh 1

# Set writable permissions on var/ directory
RUN chmod -R 775 /var/www/html/var && \
    chown -R www-data:www-data /var/www/html/var

RUN rm -rf /tmp/php/

ADD utils/build/docker/php/apache-mod/entrypoint.sh /
WORKDIR /binaries
ENTRYPOINT []
RUN echo "#!/bin/bash\ndumb-init /entrypoint.sh" > app.sh
RUN chmod +x app.sh
CMD [ "./app.sh" ]
