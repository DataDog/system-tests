#!/bin/bash

set -e

PHP_MAJOR_VERSION=$(php -r "echo PHP_MAJOR_VERSION;")
PHP_MINOR_VERSION=$(php -r "echo PHP_MINOR_VERSION;")
PHP_VERSION=$(php -r "echo PHP_MAJOR_VERSION.'.'.PHP_MINOR_VERSION;")
VARIANT=$(php-config --prefix| grep release-zts && echo release-zts || echo "")

export TRACER_VERSION=latest
export APPSEC_VERSION=latest

mkdir -p /etc/apache2/mods-available/ /var/www/html/rasp /etc/php/
cp -rf /tmp/php/apache-mod/php.conf /etc/apache2/mods-available/
cp -rf /tmp/php/apache-mod/php.load /etc/apache2/mods-available/
cp -rf /tmp/php/common/* /var/www/html/
cp -rf /tmp/php/common/install_ddtrace.sh /
cp -rf /tmp/php/common/php.ini /etc/php/

# Install required packages and PHP extensions
printf '#!/bin/sh\n\nexit 101\n' > /usr/sbin/policy-rc.d && \
	chmod +x /usr/sbin/policy-rc.d && \
	apt-get update && apt-get install -y \
		apache2 jq \
	&& rm -rf /var/lib/apt/lists/* && \
	rm -rf /usr/sbin/policy-rc.d

a2enmod rewrite

ARCH=$(arch)
if [[ $ARCH = aarch64 ]]; then
  ARCH=arm64
else
  ARCH=amd64
fi

curl -Lf -o /tmp/dumb_init.deb https://github.com/Yelp/dumb-init/releases/download/v1.2.5/dumb-init_1.2.5_${ARCH}.deb && \
	dpkg -i /tmp/dumb_init.deb && rm /tmp/dumb_init.deb

if [[ "${PHP_MAJOR_VERSION}" -ge 8 ]]; then
	sed -i "s/%PHP_MAJOR_VERSION//g" /etc/apache2/mods-available/php.{conf,load};
else
  sed -i "s/%PHP_MAJOR_VERSION/${PHP_MAJOR_VERSION}/g" /etc/apache2/mods-available/php.{conf,load};
fi

if php-config --prefix | grep -q release-zts; \
	then sed -i "s/%MPM/event/" /etc/apache2/mods-available/php.load; \
	else sed -i "s/%MPM/prefork/" /etc/apache2/mods-available/php.load; \
	fi

if ! { echo $VARIANT | grep -q zts; }; then a2dismod mpm_event; a2enmod mpm_prefork; fi

a2enmod php

sed -i s/80/7777/ /etc/apache2/ports.conf

# Install Composer
curl -sS https://getcomposer.org/installer | php -- --install-dir=/usr/local/bin --filename=composer

# Set up Monolog using Composer
cd /var/www/html
composer install --prefer-dist

# Set proper permissions
chmod -R 755 /var/www/html/vendor
find /var/www/html/vendor -type f -exec chmod 644 {} \;

/install_ddtrace.sh 1

if [[ -f "/etc/php/98-ddtrace.ini" ]]; then
    grep -E 'datadog.trace.request_init_hook|datadog.trace.sources_path' /etc/php/98-ddtrace.ini >> /etc/php/php.ini
fi
