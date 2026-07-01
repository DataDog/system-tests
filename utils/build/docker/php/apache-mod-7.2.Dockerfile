FROM datadog/system-tests:apache-mod-7.2.base-v1

ENV PHP_VERSION=7.2
ENV VARIANT=release

ADD utils/build/docker/php/apache-mod/php.conf /etc/apache2/mods-available/php.conf
RUN ln -sf /etc/apache2/mods-available/php.conf /etc/apache2/mods-enabled/php.conf
ADD utils/build/docker/php/apache-mod/entrypoint.sh /entrypoint.sh
ADD utils/build/docker/php/weblogs/plain /var/www/html
ADD utils/build/docker/php/common/rewrite-rules.conf /var/www/html/rewrite-rules.conf
ADD utils/build/docker/php/common/ffe.php /var/www/html/ffe.php
ADD utils/build/docker/php/common/php.ini /etc/php/php.ini
ADD utils/build/docker/php/common/install_ddtrace.sh /install_ddtrace.sh

ADD binaries* /binaries/
RUN /install_ddtrace.sh 1
