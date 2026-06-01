FROM datadog/system-tests:apache-mod-7.2-zts.base-v1

ENV PHP_VERSION=7.2
ENV VARIANT=release-zts

ADD utils/build/docker/php/apache-mod/php.conf /etc/apache2/mods-available/php.conf
RUN ln -sf /etc/apache2/mods-available/php.conf /etc/apache2/mods-enabled/php.conf
ADD utils/build/docker/php/apache-mod/entrypoint.sh /entrypoint.sh
ADD utils/build/docker/php/common /var/www/html
ADD utils/build/docker/php/common/php.ini /etc/php/php.ini
ADD utils/build/docker/php/common/install_ddtrace.sh /install_ddtrace.sh

ADD binaries* /binaries/
RUN /install_ddtrace.sh 1

ADD utils/build/docker/php/apache-mod/entrypoint.sh /entrypoint.sh
WORKDIR /binaries
ENTRYPOINT []
RUN echo "#!/bin/bash\nexec dumb-init /entrypoint.sh" > app.sh
RUN chmod +x app.sh
CMD [ "./app.sh" ]
