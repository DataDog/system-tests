#!/bin/bash

backend &

if [[ "${DDPROF_ENABLE:-,,}" == "yes" ]]; then
  ddprof -l notice nginx-debug -g 'daemon off;'
else
  nginx-debug -g 'daemon off;'
fi
