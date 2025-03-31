#!/bin/bash

set -e

PHP_VERSION=$1
PHP_MAJOR_VERSION=`echo $PHP_VERSION | cut -d. -f1`

apt-get update
DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends tzdata publicsuffix

printf '#!/bin/sh\n\nexit 101\n' > /usr/sbin/policy-rc.d && \
	chmod +x /usr/sbin/policy-rc.d && \
	apt-get install -y curl apache2 libapache2-mod-fcgid software-properties-common jq ca-certificates \
	&& rm -rf /var/lib/apt/lists/* && \
	rm -rf /usr/sbin/policy-rc.d

add-apt-repository ppa:ondrej/apache2 -y
add-apt-repository ppa:ondrej/php -y
apt-get update

# Install PHP and required extensions
apt-get install -y \
    php$PHP_VERSION-fpm \
    php$PHP_VERSION-curl \
    php$PHP_VERSION-json \
    php$PHP_VERSION-xml \
    php$PHP_VERSION-common \
    php$PHP_VERSION-hash \
    apache2 \
    php$PHP_VERSION-mysql \
    php$PHP_VERSION-pgsql

# Install Composer
curl -sS https://getcomposer.org/installer | php -- --install-dir=/usr/local/bin --filename=composer

# Copy PHP extensions to the correct location
PHP_EXT_DIR=$(php -i | grep "extension_dir" | head -n 1 | cut -d " " -f 3)
if [ -d "/usr/lib/php/modules" ]; then
    cp /usr/lib/php/modules/*.so $PHP_EXT_DIR/
elif [ -d "/usr/lib/php/*/modules" ]; then
    cp /usr/lib/php/*/modules/*.so $PHP_EXT_DIR/
fi

mkdir -p /var/www/html/rasp
cp -rf /tmp/php/common/*.php /var/www/html/
cp -rf /tmp/php/common/*.json /var/www/html/
cp -rf /tmp/php/common/rasp/*.php /var/www/html/rasp/
cp /tmp/php/php-fpm/php-fpm.conf /etc/apache2/conf-available/php$PHP_VERSION-fpm.conf
cp /tmp/php/common/php.ini /etc/php/$PHP_VERSION/fpm/php.ini
cp /tmp/php/php-fpm/entrypoint.sh /

# Set up Monolog using Composer
cd /var/www/html
composer require monolog/monolog:^3.5

# Set proper permissions
chmod -R 755 /var/www/html/vendor
find /var/www/html/vendor -type f -exec chmod 644 {} \;

a2enmod rewrite

a2enconf php$PHP_VERSION-fpm
a2enmod proxy
a2enmod proxy_fcgi

ARCH=$(arch)
if [[ $ARCH = aarch64 ]]; then
  ARCH=arm64
else
  ARCH=amd64
fi

curl -Lf -o /tmp/dumb_init.deb https://github.com/Yelp/dumb-init/releases/download/v1.2.5/dumb-init_1.2.5_${ARCH}.deb && \
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
echo "datadog.trace.sources_path = /opt/datadog/dd-library/$SYSTEM_TESTS_LIBRARY_VERSION/dd-trace-sources/src" >> /etc/php/$PHP_VERSION/fpm/php.ini
