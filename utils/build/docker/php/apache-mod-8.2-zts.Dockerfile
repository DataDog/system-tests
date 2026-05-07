FROM datadog/system-tests:apache-mod-8.2-zts.base-v1

ENV PHP_VERSION=8.2
ENV VARIANT=release-zts

ADD utils/build/docker/php/apache-mod/php.conf /etc/apache2/mods-available/apache-mod/php.conf
ADD utils/build/docker/php/apache-mod/php.load /etc/apache2/mods-available/apache-mod/php.load
ADD utils/build/docker/php/common /var/www/html
ADD utils/build/docker/php/common/php.ini /etc/php/php.ini
ADD utils/build/docker/php/common/install_ddtrace.sh /install_ddtrace.sh

RUN /install_ddtrace.sh 1
