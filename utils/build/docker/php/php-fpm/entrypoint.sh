#!/bin/bash -e

if [[ $# -gt 0 ]]; then
  "$@"
  exit $?
fi

export SYSTEM_TESTS_LOGS=/var/log/system-tests

# This is required to allow the tracer to open itself
chmod a+rx /root

rm -f /tmp/ddappsec.lock
LOGS_PHP=(/var/log/system-tests/appsec.log /var/log/system-tests/helper.log /var/log/system-tests/php_error.log /var/log/system-tests/tracer.log)
touch "${LOGS_PHP[@]}"
chown www-data:www-data "${LOGS_PHP[@]}"

LOGS_APACHE=(/var/log/apache2/{access.log,error.log})
touch "${LOGS_APACHE[@]}"
chown root:adm "${LOGS_APACHE[@]}"

# Unused at the moment
env | sed -rn 's#^([^=]+)=([^=]+)$#env[\1] = "\2"#p' | tee /dev/stderr >> /etc/php/PHP_VERSION/fpm/pool.d/www.conf
sed -i "s/;clear_env = no/clear_env = no/" /etc/php/PHP_VERSION/fpm/pool.d/www.conf

service apache2 start
# Use init script to preserve environment
/etc/init.d/phpPHP_VERSION-fpm start

fpm_pid=$(pgrep -f '^php-fpm: master process')
apache_pid=$(cat /var/run/apache2/apache2.pid)
ffe_pid=""
if [[ ${SYSTEM_TESTS_FFE_SHUTDOWN_FLUSH_ENABLED:-} == "true" ]]; then
  DD_TRACE_CLI_ENABLED=true php /var/www/html/ffe_shutdown_worker.php &
  ffe_pid=$!
fi

shutdown() {
  trap '' TERM INT
  apache2ctl -k graceful-stop
  kill -QUIT "$fpm_pid"
  while kill -0 "$apache_pid" 2>/dev/null || kill -0 "$fpm_pid" 2>/dev/null; do
    sleep 0.05
  done
  if [[ -n "$ffe_pid" ]]; then
    kill -TERM "$ffe_pid"
    wait "$ffe_pid"
  fi
  kill "$logs_pid" 2>/dev/null || true
  wait "$logs_pid" 2>/dev/null || true
  exit 0
}
trap shutdown TERM INT

tail -f "${LOGS_PHP[@]}" "${LOGS_APACHE[@]}" &
logs_pid=$!
wait "$logs_pid"
