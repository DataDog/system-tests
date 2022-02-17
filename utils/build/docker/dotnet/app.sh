#!/bin/bash

set -eu

echo "Receiver socket is ${DD_APM_RECEIVER_SOCKET:-NOT_SET}"
bash /system-tests/utils/scripts/configure-container-options.sh
dotnet app.dll
