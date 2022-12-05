#!/bin/bash

ddprof -l notice -u 30 stress-ng -c 1 -t 60s &

if [[ "${DDPROF_ENABLE:-,,}" == "yes" ]]; then
  ddprof -l notice nginx -g 'daemon off;'
else
  nginx -g 'daemon off;'
fi
