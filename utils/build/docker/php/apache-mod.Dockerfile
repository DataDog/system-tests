ARG PHP_VERSION=8.0
ARG VARIANT=release-zts

FROM datadog/dd-appsec-php-ci:php-$PHP_VERSION-$VARIANT

RUN printf '#!/bin/sh\n\nexit 101\n' > /usr/sbin/policy-rc.d && \
	chmod +x /usr/sbin/policy-rc.d && \
	apt-get update && apt-get install -y \
		apache2 \
	&& rm -rf /var/lib/apt/lists/* && \
	rm -rf /usr/sbin/policy-rc.d

RUN find /var/www/html -mindepth 1 -delete
RUN echo '<?php phpinfo();' > /var/www/html/index.php
RUN echo '<?php echo "OK";' > /var/www/html/sample_rate_route.php
RUN echo '<?php echo "Hello, WAF!";' > /var/www/html/waf.php
RUN echo '<?php http_response_code(404);' > /var/www/html/404.php
RUN a2enmod rewrite

ENV DD_TRACE_ENABLED=1
ENV DD_TRACE_GENERATE_ROOT_SPAN=1
ENV DD_TRACE_AGENT_FLUSH_AFTER_N_REQUESTS=0
ENV DD_TRACE_DEBUG=1
ENV DD_APPSEC_ENABLED=1
ENV DD_TRACE_SAMPLE_RATE=0.5
ENV DD_TAGS='key1:val1, aKey : aVal bKey:bVal cKey:'

RUN curl -Lf -o /tmp/dumb_init.deb https://github.com/Yelp/dumb-init/releases/download/v1.2.5/dumb-init_1.2.5_amd64.deb && \
	dpkg -i /tmp/dumb_init.deb && rm /tmp/dumb_init.deb

ARG PHP_VERSION=8.0
ARG VARIANT=release-zts
ADD utils/build/docker/php/php.conf /etc/apache2/mods-available/
ADD utils/build/docker/php/php.load /etc/apache2/mods-available/
RUN /bin/bash -c 'if [[ "${PHP_VERSION:0:1}" -ge 8 ]]; then sed -i "s/%PHP_MAJOR_VERSION//g" /etc/apache2/mods-available/php.{conf,load}; else \
  sed -i "s/%PHP_MAJOR_VERSION/${PHP_VERSION:0:1}/g" /etc/apache2/mods-available/php.{conf,load}; fi'
RUN if echo $VARIANT | grep -q zts; \
	then sed -i "s/%MPM/event/" /etc/apache2/mods-available/php.load; \
	else sed -i "s/%MPM/prefork/" /etc/apache2/mods-available/php.load; \
	fi
RUN if ! { echo $VARIANT | grep -q zts; }; then a2dismod mpm_event; a2enmod mpm_prefork; fi
RUN a2enmod php

RUN sed -i s/80/7777/ /etc/apache2/ports.conf
EXPOSE 7777/tcp

ADD binaries* /binaries/
ADD utils/build/docker/php/install_ddtrace.sh /
RUN /install_ddtrace.sh

ADD utils/build/docker/php/entrypoint.sh /
ADD utils/build/docker/php/php.ini /etc/php/

WORKDIR /binaries
ENTRYPOINT ["dumb-init", "/entrypoint.sh"]
