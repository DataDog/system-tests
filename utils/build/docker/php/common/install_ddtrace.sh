#!/bin/bash

set -eux

IS_APACHE=${1:-0}

cd /binaries

PKG=$(find /binaries -maxdepth 1 -name 'dd-library-php-*-linux-gnu.tar.gz')
SETUP=/binaries/datadog-setup.php

DDTRACE_SO=/binaries/ddtrace.so
DDAPPSEC_SO=/binaries/ddappsec.so
APPSEC_HELPER_SO=/binaries/libddappsec-helper.so
LIBDDWAF_SO=/binaries/libddwaf.so

# Determine INI file location
INI_FILE=/etc/php/php.ini
if [ -d /opt/php/nts ]; then
  INI_FILE=/opt/php/nts/php.ini
elif [[ $IS_APACHE -eq 0 ]]; then
  PHP_VERSION=$(php -r "echo PHP_MAJOR_VERSION.'.'.PHP_MINOR_VERSION;")
  INI_FILE=/etc/php/$PHP_VERSION/fpm/conf.d/98-ddtrace.ini
  mkdir -p $(dirname $INI_FILE)
  chmod 777 $(dirname $INI_FILE)
fi

# Always install from package first (to get recommended.json and other files)
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

EXTRA_ARGS=""
PHP_VERSION=$(php -r "echo PHP_MAJOR_VERSION.'.'.PHP_MINOR_VERSION;")
if [ "$(printf '%s\n' "7.1" "$PHP_VERSION" | sort -V | head -n1)" = "7.1" ]; then
  EXTRA_ARGS="--enable-profiling"
fi

INI_FILE=/etc/php/php.ini
echo "Installing php package ${PKG-"{default}"} with setup script $SETUP"
if [[ $IS_APACHE -eq 0 ]]; then
      php $SETUP --php-bin all ${PKG+"--file=$PKG"} ${EXTRA_ARGS}
      PHP_VERSION=$(php -r "echo PHP_MAJOR_VERSION.'.'.PHP_MINOR_VERSION;")
      INI_FILE=/etc/php/$PHP_VERSION/fpm/conf.d/98-ddtrace.ini
else
      PHP_INI_SCAN_DIR="/etc/php" php $SETUP --php-bin all ${PKG+"--file=$PKG"} ${EXTRA_ARGS}
fi

# After package installation, override with custom ddtrace.so if present
if [ -f $DDTRACE_SO ]; then
  echo "Overriding package ddtrace.so with custom binary from $DDTRACE_SO"
  # Find and replace the installed ddtrace.so with custom one
  INSTALLED_DDTRACE=$(find /root /opt -name ddtrace.so 2>/dev/null | grep -v /binaries | head -1)
  if [ -n "$INSTALLED_DDTRACE" ]; then
    echo "Found installed ddtrace.so at $INSTALLED_DDTRACE, replacing with custom binary"
    cp -f $DDTRACE_SO $INSTALLED_DDTRACE
  else
    echo "Warning: Could not find installed ddtrace.so to replace"
  fi
fi

# After package installation, override with custom ddappsec.so and helper if present
if [ -f $DDAPPSEC_SO ] && [ -f $APPSEC_HELPER_SO ]; then
  echo "Overriding package ddappsec.so and helper with custom binaries"
  # Find and replace the installed ddappsec.so
  INSTALLED_DDAPPSEC=$(find /root /opt -name ddappsec.so 2>/dev/null | grep -v /binaries | head -1)
  if [ -n "$INSTALLED_DDAPPSEC" ]; then
    echo "Found installed ddappsec.so at $INSTALLED_DDAPPSEC, replacing with custom binary"
    cp -f $DDAPPSEC_SO $INSTALLED_DDAPPSEC
  else
    echo "Warning: Could not find installed ddappsec.so to replace"
  fi

  # Find and replace the installed helper
  INSTALLED_HELPER=$(find /root /opt -name libddappsec-helper.so 2>/dev/null | grep -v /binaries | head -1)
  if [ -n "$INSTALLED_HELPER" ]; then
    echo "Found installed helper at $INSTALLED_HELPER, replacing with custom binary"
    cp -f $APPSEC_HELPER_SO $INSTALLED_HELPER
  else
    echo "Warning: Could not find installed libddappsec-helper.so to replace"
  fi
fi

if [ -f $LIBDDWAF_SO ]; then
  echo "Copying libddwaf.so from /binaries"
  INSTALLED_HELPER=$(find /root /opt -name libddappsec-helper.so 2>/dev/null | grep -v /binaries | head -1)
  if [ -n "$INSTALLED_HELPER" ]; then
    echo "Found installed helper at $INSTALLED_HELPER, installing custom libddwaf.so alongside"
    cp -v $LIBDDWAF_SO "$(dirname "$INSTALLED_HELPER")"
  else
    echo "Warning: Could not find installed libddappsec-helper.so"
  fi
fi


if test -f $INI_FILE; then
  #There is a bug on 0.98.1 which disable explicitly appsec when it shouldnt. Delete this line when hotfix
  sed -i "/datadog.appsec.enabled/s/^/;/g" $INI_FILE
  #Parametric tests don't need appsec
  [ ! -z ${NO_EXTRACT_VERSION+x} ] && echo "datadog.appsec.enabled = Off" >> $INI_FILE
fi

#Ensure parametric test compatibility
[ ! -z ${NO_EXTRACT_VERSION+x} ] && exit 0

#Extract version info
php -d error_reporting='' -d extension=ddtrace.so -d extension=ddappsec.so -r 'echo phpversion("ddtrace");' > \
  /binaries/SYSTEM_TESTS_LIBRARY_VERSION


find /opt -name ddappsec-helper -exec ln -s '{}' /usr/local/bin/ \;
mkdir -p /etc/dd-appsec
find /opt -name recommended.json -exec ln -s '{}' /etc/dd-appsec/ \;

rm -rf /tmp/{dd-library-php-setup.php,dd-library,dd-appsec}
