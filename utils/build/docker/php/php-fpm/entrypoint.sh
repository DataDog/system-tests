#!/bin/bash -e

if [[ $# -gt 0 ]]; then
  "$@"
  exit $?
fi

rm -f /tmp/ddappsec.lock
LOGS_PHP=(/tmp/appsec.log /tmp/helper.log /tmp/php_error.log)
touch "${LOGS_PHP[@]}"
chown www-data:www-data "${LOGS_PHP[@]}"

LOGS_APACHE=(/var/log/apache2/{access.log,error.log})
touch "${LOGS_APACHE[@]}"
chown root:adm "${LOGS_APACHE[@]}"

# Unused at the moment
env | sed -rn 's#^([^=]+)=([^=]+)$#env[\1] = \2#p' | tee /dev/stderr >> /etc/php/8.0/fpm/pool.d/www.conf
sed -i "s/;clear_env = no/clear_env = no/" /etc/php/8.0/fpm/pool.d/www.conf

service apache2 start
# Use init script to preserve environment
/etc/init.d/php8.0-fpm start

exec tail -f "${LOGS_PHP[@]}" "${LOGS_APACHE[@]}"
