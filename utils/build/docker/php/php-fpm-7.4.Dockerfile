
FROM datadog/system-tests:php-fpm-7.4.base-v1

ARG PHP_VERSION=7.4

ADD utils/build/docker/php/common/ /var/www/html/
ADD utils/build/docker/php/common/php.ini /etc/php/$PHP_VERSION/fpm/php.ini
ADD utils/build/docker/php/php-fpm/php-fpm.conf /etc/apache2/conf-available/php$PHP_VERSION-fpm.conf
ADD utils/build/docker/php/php-fpm/entrypoint.sh /entrypoint.sh
RUN sed -i s/PHP_VERSION/$PHP_VERSION/ /entrypoint.sh
RUN sed -i s/PHP_VERSION/$PHP_VERSION/ /etc/apache2/conf-available/php$PHP_VERSION-fpm.conf
RUN sed -i s/PHP_MAJOR_VERSION/$PHP_MAJOR_VERSION/ /etc/apache2/conf-available/php$PHP_VERSION-fpm.conf

RUN chmod 644 /var/www/html/*.php

ADD binaries* /binaries/
ADD utils/build/docker/php/common/install_ddtrace.sh /

RUN /install_ddtrace.sh 0
RUN rm -rf /etc/php/$PHP_VERSION/fpm/conf.d/98-ddappsec.ini

RUN SYSTEM_TESTS_LIBRARY_VERSION=$(cat /binaries/SYSTEM_TESTS_LIBRARY_VERSION) && \
    echo "datadog.trace.request_init_hook = /opt/datadog/dd-library/$SYSTEM_TESTS_LIBRARY_VERSION/dd-trace-sources/bridge/dd_wrap_autoloader.php" >> /etc/php/$PHP_VERSION/fpm/php.ini && \
    echo "datadog.trace.sources_path = /opt/datadog/dd-library/$SYSTEM_TESTS_LIBRARY_VERSION/dd-trace-sources/src" >> /etc/php/$PHP_VERSION/fpm/php.ini

EXPOSE 7777/tcp

WORKDIR /binaries
ENTRYPOINT []
RUN echo "#!/bin/bash\ndumb-init /entrypoint.sh" > app.sh
RUN chmod +x app.sh
CMD [ "./app.sh" ]
