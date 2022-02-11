#!/bin/bash

bash /system-tests/utils/scripts/configure-container-options.sh
dumb-init /entrypoint.sh
