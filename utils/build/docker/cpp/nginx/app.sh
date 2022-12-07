#!/bin/bash

if [[ "${DDPROF_ENABLE:-,,}" == "yes" ]]; then
  ddprof -l notice nginx -g 'daemon off;'
else
  nginx -g 'daemon off;'
fi
