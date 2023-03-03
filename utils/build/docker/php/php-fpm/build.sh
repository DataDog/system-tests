#!/bin/bash

set -e

PHP_VERSION=$1
PHP_MAJOR_VERSION=`echo $PHP_VERSION | cut -d. -f1`

apt-get update
DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends tzdata publicsuffix

printf '#!/bin/sh\n\nexit 101\n' > /usr/sbin/policy-rc.d && \
	chmod +x /usr/sbin/policy-rc.d && \
	apt-get install -y curl apache2 libapache2-mod-fcgid software-properties-common jq \
	&& rm -rf /var/lib/apt/lists/* && \
	rm -rf /usr/sbin/policy-rc.d


add-apt-repository ppa:ondrej/php -y
apt-get update

apt-get install -y php$PHP_VERSION-fpm php$PHP_VERSION-curl

find /var/www/html -mindepth 1 -delete


cp -rf /tmp/php/common/*.php /var/www/html/
cp /tmp/php/php-fpm/php-fpm.conf /etc/apache2/conf-available/php$PHP_VERSION-fpm.conf
cp /tmp/php/common/php.ini /etc/php/$PHP_VERSION/fpm/php.ini
cp /tmp/php/php-fpm/entrypoint.sh /

a2enmod rewrite

a2enconf php$PHP_VERSION-fpm
a2enmod proxy
a2enmod proxy_fcgi


curl -Lf -o /tmp/dumb_init.deb https://github.com/Yelp/dumb-init/releases/download/v1.2.5/dumb-init_1.2.5_amd64.deb && \
	dpkg -i /tmp/dumb_init.deb && rm /tmp/dumb_init.deb

sed -i s/80/7777/ /etc/apache2/ports.conf
sed -i s/PHP_VERSION/$PHP_VERSION/ /entrypoint.sh
sed -i s/PHP_VERSION/$PHP_VERSION/ /etc/apache2/conf-available/php$PHP_VERSION-fpm.conf
sed -i s/PHP_MAJOR_VERSION/$PHP_MAJOR_VERSION/ /etc/apache2/conf-available/php$PHP_VERSION-fpm.conf

export TRACER_VERSION=latest
export APPSEC_VERSION=latest
cp /tmp/php/common/install_ddtrace.sh /
/install_ddtrace.sh 0

rm -rf /etc/php/$PHP_VERSION/fpm/conf.d/98-ddappsec.ini

SYSTEM_TESTS_LIBRARY_VERSION=$(cat /binaries/SYSTEM_TESTS_LIBRARY_VERSION)
echo "datadog.trace.request_init_hook = /opt/datadog/dd-library/$SYSTEM_TESTS_LIBRARY_VERSION/dd-trace-sources/bridge/dd_wrap_autoloader.php" >> /etc/php/$PHP_VERSION/fpm/php.ini
