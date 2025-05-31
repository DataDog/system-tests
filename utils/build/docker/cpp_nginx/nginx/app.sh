#!/bin/bash

backend &

if [[ $DD_TRACE_DEBUG = true ]]; then
  sed -i 's/\(error_log [^ ]* \)info;/\1debug;/' /etc/nginx/nginx.conf
  NGINX_BINARY=nginx-debug
else
  NGINX_BINARY=nginx
fi

if [[ "${DDPROF_ENABLE:-,,}" == "yes" ]]; then
  ddprof -l notice "$NGINX_BINARY" -g 'daemon off;'
else
  "$NGINX_BINARY" -g 'daemon off;'
fi
