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

# Fix the timeout
if [[ -n "$DD_APPSEC_WAF_TIMEOUT" ]]; then
    value=${DD_APPSEC_WAF_TIMEOUT//[a-zA-Z]/}
    unit=${DD_APPSEC_WAF_TIMEOUT//[0-9]/}

    case $unit in
        s)
            let value=value*1000
            ;;
        us)
            if [[ $value -lt 1000 ]]; then
                value=1
            else
                let value=value/1000
            fi
            ;;
    esac
    export DD_APPSEC_WAF_TIMEOUT=$value
fi

export -p | sed 's@declare -x@export@' | tee /dev/stderr >> /etc/apache2/envvars

service apache2 start

exec tail -f "${LOGS_PHP[@]}" "${LOGS_APACHE[@]}"
