#!/usr/bin/env bash
set -eu

if [[ "${DDPROF_ENABLE:-,,}" == "yes" ]]; then
  exec ddprof -l notice nginx -g 'daemon off;'
else
  exec nginx -g 'daemon off;'
fi
