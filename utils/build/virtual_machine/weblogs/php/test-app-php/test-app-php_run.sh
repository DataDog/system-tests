#!/bin/bash
echo "START php APP"

set -e

WEBLOG_LOG_DIR="/var/log/datadog_weblog"

# PHP host apps (especially with profiling) can segfault at startup.
# Enable core dumps before any php invocation so the crash produces a file
# that download_vm_logs can pull from the AWS machine.
enable_coredumps() {
    sudo mkdir -p "${WEBLOG_LOG_DIR}"
    sudo chmod 777 "${WEBLOG_LOG_DIR}"
    ulimit -c unlimited || true
    echo 1 | sudo tee /proc/sys/fs/suid_dumpable >/dev/null || true
    echo "${WEBLOG_LOG_DIR}/core.%e.%p" | sudo tee /proc/sys/kernel/core_pattern >/dev/null || true
}

chmod_cores() {
    find "${WEBLOG_LOG_DIR}" -maxdepth 1 -type f -name 'core*' -exec sudo chmod a+r {} \; 2>/dev/null || true
}

trap chmod_cores EXIT

# shellcheck disable=SC2035
sudo chmod -R 755 *

sudo cp index.php /home/datadog/

enable_coredumps

echo "Testing weblog with php version:"
# sudo resets ulimit, so raise it in the same root shell that runs php
sudo sh -c 'ulimit -c unlimited; php --version'
./create_and_run_app_service.sh "php -S 0.0.0.0:5985"
echo "RUN AFTER THE SERVICE"
cat test-app.service
echo "RUN php DONE"
