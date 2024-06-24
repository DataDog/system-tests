#!/bin/bash

set -eux

IS_APACHE=${1:-0}

cd /binaries

PKG=$(find /binaries -maxdepth 1 -name 'dd-library-php-*-linux-gnu.tar.gz')
SETUP=/binaries/datadog-setup.php

if [ "$PKG" != "" ] && [ ! -f "$SETUP" ]; then
    echo "local install failed: package located in /binaries but datadog-setup.php not present, please include it"
    exit 1
fi

if [ "$PKG" == "" ]; then
    #Download latest release
    curl -LO https://github.com/DataDog/dd-trace-php/releases/latest/download/datadog-setup.php
    SETUP=datadog-setup.php
    unset PKG
fi

INI_FILE=/etc/php/php.ini
echo "Installing php package ${PKG-"{default}"} with setup script $SETUP"
if [[ $IS_APACHE -eq 0 ]]; then
    php $SETUP --php-bin all ${PKG+"--file=$PKG"}
    PHP_VERSION=$(php -r "echo PHP_MAJOR_VERSION.'.'.PHP_MINOR_VERSION;")
    INI_FILE=/etc/php/$PHP_VERSION/fpm/conf.d/98-ddtrace.ini
else
    PHP_INI_SCAN_DIR="/etc/php" php $SETUP --php-bin all ${PKG+"--file=$PKG"}
fi

if test -f $INI_FILE; then
    #There is a bug on 0.98.1 which disable explicitly appsec when it shouldnt. Delete this line when hotfix
    sed -i "/datadog.appsec.enabled/s/^/;/g" $INI_FILE
    #Parametric tests don't need appsec
    [ ! -z ${NO_EXTRACT_VERSION+x} ] && echo "datadog.appsec.enabled = Off" >>$INI_FILE
fi

#Ensure parametric test compatibility
[ ! -z ${NO_EXTRACT_VERSION+x} ] && exit 0

#Extract version info
php -d error_reporting='' -d extension=ddtrace.so -d extension=ddappsec.so -r 'echo phpversion("ddtrace");' > \
    /binaries/SYSTEM_TESTS_LIBRARY_VERSION

touch SYSTEM_TESTS_LIBDDWAF_VERSION

library_version=$(<././SYSTEM_TESTS_LIBRARY_VERSION)
rule_file="/opt/datadog/dd-library/${library_version}/etc/recommended.json"

jq -r '.metadata.rules_version // "1.2.5"' "${rule_file}" >SYSTEM_TESTS_APPSEC_EVENT_RULES_VERSION

find /opt -name ddappsec-helper -exec ln -s '{}' /usr/local/bin/ \;
mkdir -p /etc/dd-appsec
find /opt -name recommended.json -exec ln -s '{}' /etc/dd-appsec/ \;

rm -rf /tmp/{dd-library-php-setup.php,dd-library,dd-appsec}
