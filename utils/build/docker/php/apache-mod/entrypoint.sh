#!/bin/bash -e

if [[ $# -gt 0 ]]; then
  "$@"
  exit $?
fi

# This is required to allow the tracer to open itself
chmod a+rx /root

rm -f /tmp/ddappsec.lock
LOGS_PHP=(/var/log/system-tests/appsec.log /var/log/system-tests/helper.log /var/log/system-tests/php_error.log /var/log/system-tests/sidecar.log /var/log/system-tests/tracer.log)
touch "${LOGS_PHP[@]}"
chown www-data:www-data "${LOGS_PHP[@]}"

LOGS_APACHE=(/var/log/apache2/{access.log,error.log})
touch "${LOGS_APACHE[@]}"
chown root:adm "${LOGS_APACHE[@]}"

#sed -i 's/StartServers.*/StartServers 1/' /etc/apache2/mods-enabled/mpm_prefork.conf
#sed -i 's/MinSpareServers.*/MinSpareServers 1/' /etc/apache2/mods-enabled/mpm_prefork.conf
#sed -i 's/MaxSpareServers.*/MaxSpareServers 1/' /etc/apache2/mods-enabled/mpm_prefork.conf

export _DD_DEBUG_SIDECAR_LOG_METHOD=file:///var/log/system-tests/sidecar.log
export _DD_SHARED_LIB_DEBUG=0
export -p | sed 's@declare -x@export@' | tee /dev/stderr >> /etc/apache2/envvars

service apache2 start

exec tail -f "${LOGS_PHP[@]}" "${LOGS_APACHE[@]}" "/var/log/system-tests/appsec.log" "/var/log/system-tests/helper.log"
