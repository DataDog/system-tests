#!/bin/bash

set -e

PHP_VERSION=$1
PHP_MAJOR_VERSION=`echo $PHP_VERSION | cut -d. -f1`

# Override apt sources to avoid backpports, restricted and multiverse (speed up update runs).
cp /tmp/php/apt-sources.d/ubuntu.sources /etc/apt/sources.list.d/

# Non-interactive mode for all apt commands.
export DEBIAN_FRONTEND=noninteractive

# Install nala (https://github.com/volitank/nala) for mirror selection and parallelization.
# nala initiates 3 parallel downloads per mirror.
apt-get update
apt-get install -y nala

# To use additional mirrors, selected by lowest latency probe, uncomment the following.
# However, the time to probe mirrors, plus the chance of selecting an improperly sync'd
# mirror, make this sometimes more unreliable than relying on our defaults.
#   nala fetch --auto --country US --country FR
#   sed -i -e 's~ restricted~~g' -e 's~ multiverse ~~g' /etc/apt/sources.list.d/nala-sources.list

# Install PPAs
cp /tmp/php/apt-sources.d/ondrej-ubuntu-{php,apache2}-noble.sources /etc/apt/sources.list.d/

nala update

# exit 101 here prevents services from starting automatically during install
printf '#!/bin/sh\n\nexit 101\n' > /usr/sbin/policy-rc.d
chmod +x /usr/sbin/policy-rc.d

nala install -y --no-install-recommends tzdata publicsuffix curl apache2 libapache2-mod-fcgid jq ca-certificates git php$PHP_VERSION-fpm php$PHP_VERSION-curl apache2 php$PHP_VERSION-mysql php$PHP_VERSION-pgsql php$PHP_VERSION-xml php$PHP_VERSION-mongodb

rm -rf /usr/sbin/policy-rc.d
rm -rf /var/lib/apt/lists/*

find /var/www/html -mindepth 1 -delete

mkdir -p /var/www/html/rasp
cp -rf /tmp/php/common/* /var/www/html/
cp /tmp/php/php-fpm/php-fpm.conf /etc/apache2/conf-available/php$PHP_VERSION-fpm.conf
cp /tmp/php/common/php.ini /etc/php/$PHP_VERSION/fpm/php.ini
cp /tmp/php/php-fpm/entrypoint.sh /

chmod 644 /var/www/html/*.php

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

# Install Composer
curl -sS https://getcomposer.org/installer | php -- --install-dir=/usr/local/bin --filename=composer

cd /var/www/html
# Use composer.json for PHP < 8.2, composer.gte8.2.json for PHP >= 8.2 (COMPOSER env = config filename)
export COMPOSER=composer.json
if [ "$(printf '%s\n' "$PHP_VERSION" "8.2" | sort -V | head -n1)" = "8.2" ]; then
	export COMPOSER=composer.gte8.2.json
fi
echo "Using composer config: $COMPOSER"
composer install --prefer-dist

# Install OTel SDK for PHP 8.1+ (open-telemetry/context requires PHP ^8.1)
# DDTrace hooks into the SDK when DD_TRACE_OTEL_ENABLED=true, bridging OTel context
# with DDTrace context so that Baggage::getCurrent() and activate() work correctly.
PHP_MINOR_VERSION=$(echo $PHP_VERSION | cut -d. -f2)
if [[ "${PHP_MAJOR_VERSION}" -ge 8 ]] && [[ "${PHP_MINOR_VERSION}" -ge 1 ]]; then
    composer require "open-telemetry/sdk:^1.0.0" --prefer-dist --no-interaction
fi


# Set proper permissions
chmod -R 755 /var/www/html/vendor
find /var/www/html/vendor -type f -exec chmod 644 {} \;

