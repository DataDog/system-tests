#!/bin/bash

backend &

if [[ $DD_TRACE_DEBUG = true ]]; then
  sed -i 's/\(error_log [^ ]* \)info;/\1debug;/' /etc/nginx/nginx.conf
fi

# ddprof is not in a tracer, it is a wrapper around executable
if [[ "${DD_PROFILING_ENABLED:-,,}" == "true" ]]; then
  ddprof -l notice nginx -g 'daemon off;'
else
  nginx -g 'daemon off;'
fi
