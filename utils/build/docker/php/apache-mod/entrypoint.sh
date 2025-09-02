#!/bin/bash -e

if [[ $# -gt 0 ]]; then
  "$@"
  exit $?
fi

# This is required to allow the tracer to open itself
chmod a+rx /root

export SYSTEM_TESTS_LOGS=/var/log/system-tests

rm -f /tmp/ddappsec.lock
LOGS_PHP=($SYSTEM_TESTS_LOGS/appsec.log $SYSTEM_TESTS_LOGS/helper.log $SYSTEM_TESTS_LOGS/php_error.log $SYSTEM_TESTS_LOGS/sidecar.log $SYSTEM_TESTS_LOGS/tracer.log)
touch "${LOGS_PHP[@]}"
chown www-data:www-data "${LOGS_PHP[@]}"

export APACHE_LOG_DIR="$SYSTEM_TESTS_LOGS/apache2"
mkdir -p "$APACHE_LOG_DIR"
LOGS_APACHE=($APACHE_LOG_DIR/{access.log,error.log})
touch "${LOGS_APACHE[@]}"
chown root:adm "${LOGS_APACHE[@]}"

if [[ "$DD_TRACE_DEBUG" == "true" ]]; then
  # if DD_TRACE_DEBUG is activated, also active apache debug logs
  sed -i 's/LogLevel warn/LogLevel debug/' /etc/apache2/apache2.conf
  # and appsec logs
  sed -i 's/.*datadog\.appsec\.log_level.*/datadog.appsec.log_level=debug/' /etc/php/php.ini
  # and helper debug logs
  sed -i 's/.*datadog\.appsec\.helper_log_level.*/datadog.appsec.helper_log_level=debug/' /etc/php/php.ini
fi

# Enable core dumps, and write them in $SYSTEM_TESTS_LOGS
echo "$SYSTEM_TESTS_LOGS/core.%p" > /proc/sys/kernel/core_pattern
sysctl -w fs.suid_dumpable=1


#sed -i 's/MinSpareServers.*/MinSpareServers 1/' /etc/apache2/mods-enabled/mpm_prefork.conf
#sed -i 's/MaxSpareServers.*/MaxSpareServers 1/' /etc/apache2/mods-enabled/mpm_prefork.conf

export _DD_DEBUG_SIDECAR_LOG_METHOD="file://$SYSTEM_TESTS_LOGS/sidecar.log"
export _DD_SHARED_LIB_DEBUG=0
export -p | sed 's@declare -x@export@' | tee /dev/stderr >> /etc/apache2/envvars

service apache2 start

exec tail -f "${LOGS_PHP[@]}" "${LOGS_APACHE[@]}" "$SYSTEM_TESTS_LOGS/appsec.log" "$SYSTEM_TESTS_LOGS/helper.log" "$SYSTEM_TESTS_LOGS/apache.strace" "$SYSTEM_TESTS_LOGS/php_error.log"
