FROM datadog/system-tests:apache-mod-7.2.base-v1

ENV PHP_VERSION=7.2
ENV VARIANT=release

ADD utils/build/docker/php/apache-mod/php.conf /etc/apache2/mods-available/apache-mod/php.conf
ADD utils/build/docker/php/apache-mod/php.load /etc/apache2/mods-available/apache-mod/php.load
ADD utils/build/docker/php/common /var/www/html
ADD utils/build/docker/php/common/php.ini /etc/php/php.ini
ADD utils/build/docker/php/common/install_ddtrace.sh /install_ddtrace.sh

ADD binaries* /binaries/
RUN /install_ddtrace.sh 1
