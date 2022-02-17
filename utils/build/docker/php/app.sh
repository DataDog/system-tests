#!/bin/bash

set -eu

bash /system-tests/utils/scripts/configure-container-options.sh
dumb-init /entrypoint.sh
