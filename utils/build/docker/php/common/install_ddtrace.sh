#!/bin/bash

set -eux

IS_APACHE=$1

cd /binaries

if [[ -f "datadog-setup.php" ]]; then
    INSTALLER_ARGS=()

    BINARIES_COMBINED_N=$(find . -name 'dd-library-php-*x86_64-linux-gnu.tar.gz' | wc -l)
    if [[ $BINARIES_COMBINED_N -eq 1 ]]; then
      INSTALLER_ARGS+=(--file dd-library-php-*x86_64-linux-gnu.tar.gz)
    elif [[ $BINARIES_COMBINED_N -gt 1 ]]; then
      echo "Too many PHP packages in /binaries" >&2
      exit 1
    fi

    echo "Install args are ${INSTALLER_ARGS[@]}"

    export DD_APPSEC_ENABLED=0
    if [[ $IS_APACHE -eq 0 ]]; then
      php datadog-setup.php --php-bin all "${INSTALLER_ARGS[@]}"
    else
      PHP_INI_SCAN_DIR="/etc/php" php datadog-setup.php --php-bin all "${INSTALLER_ARGS[@]}"
    fi
else
    echo "Loading install script"

    curl -Lf -o /tmp/dd-library-php-setup.php \
      https://github.com/DataDog/dd-trace-php/releases/latest/download/datadog-setup.php

    # Full installation: APM + ASM + Profiling (Beta)
    INSTALLER_ARGS=()
    INSTALLER_ARGS+=(--enable-appsec)
    INSTALLER_ARGS+=(--enable-profiling)

    echo "Install args are ${INSTALLER_ARGS[@]}"

    export DD_APPSEC_ENABLED=0
    if [[ $IS_APACHE -eq 0 ]]; then
      php /tmp/dd-library-php-setup.php \
        "${INSTALLER_ARGS[@]}"\
        --php-bin all
    else
      PHP_INI_SCAN_DIR="/etc/php" php /tmp/dd-library-php-setup.php \
        "${INSTALLER_ARGS[@]}"\
        --php-bin all
    fi
fi

php -d error_reporting='' -d extension=ddtrace.so -d extension=ddappsec.so -r 'echo phpversion("ddtrace");' > \
  ./SYSTEM_TESTS_LIBRARY_VERSION

php -d error_reporting='' -d extension=ddtrace.so -d extension=ddappsec.so -r 'echo phpversion("ddappsec");' > \
  ./SYSTEM_TESTS_PHP_APPSEC_VERSION

touch SYSTEM_TESTS_LIBDDWAF_VERSION

library_version=$(<././SYSTEM_TESTS_LIBRARY_VERSION)
rule_file="/opt/datadog/dd-library/${library_version}/etc/recommended.json"
if [[ ! -f "${rule_file}" ]]; then
    appsec_version=$(<./SYSTEM_TESTS_PHP_APPSEC_VERSION)
    rule_file="/opt/datadog/dd-library/appsec-${appsec_version}/etc/dd-appsec/recommended.json"
fi

jq -r '.metadata.rules_version // "1.2.5"' "${rule_file}" > SYSTEM_TESTS_APPSEC_EVENT_RULES_VERSION

find /opt -name ddappsec-helper -exec ln -s '{}' /usr/local/bin/ \;
mkdir -p /etc/dd-appsec
find /opt -name recommended.json -exec ln -s '{}' /etc/dd-appsec/ \;

rm -rf /tmp/{dd-library-php-setup.php,dd-library,dd-appsec}
