#!/bin/bash
echo "START php APP"

set -e

WEBLOG_LOG_DIR="/var/log/datadog_weblog"
CORE_DUMP_OVERRIDE="/etc/systemd/system/test-app.service.d/core-dumps.conf"

enable_core_dumps() {
    sudo mkdir -p "${WEBLOG_LOG_DIR}"
    sudo chmod 777 "${WEBLOG_LOG_DIR}"

    # PHP is first invoked through sudo, so allow privileged processes to dump.
    if ! printf '%s\n' 1 | sudo tee /proc/sys/fs/suid_dumpable >/dev/null; then
        echo "WARNING: Could not enable core dumps for privileged PHP processes" >&2
    fi
    if ! printf '%s\n' "${WEBLOG_LOG_DIR}/core.%e.%p" |
        sudo tee /proc/sys/kernel/core_pattern >/dev/null; then
        echo "WARNING: Could not configure the PHP core dump destination" >&2
    fi

    # The PHP server runs under systemd and does not inherit this script's limits.
    if ! sudo mkdir -p "$(dirname "${CORE_DUMP_OVERRIDE}")" ||
        ! printf '%s\n' "[Service]" "LimitCORE=infinity" |
            sudo tee "${CORE_DUMP_OVERRIDE}" >/dev/null; then
        echo "WARNING: Could not remove the core dump limit from test-app.service" >&2
    fi

    {
        printf 'core_pattern: '
        cat /proc/sys/kernel/core_pattern 2>/dev/null || echo unknown
        printf 'suid_dumpable: '
        cat /proc/sys/fs/suid_dumpable 2>/dev/null || echo unknown
        if sudo test -f "${CORE_DUMP_OVERRIDE}"; then
            printf 'test-app.service LimitCORE: infinity\n'
        else
            printf 'test-app.service LimitCORE: unavailable\n'
        fi
    } | sudo tee "${WEBLOG_LOG_DIR}/core-diagnostics.txt" >/dev/null || true
}

# shellcheck disable=SC2035
sudo chmod -R 755 *

sudo cp index.php /home/datadog/

enable_core_dumps

echo "Testing weblog with php version:"
# sudo starts a fresh shell, so set the limit in the process that launches PHP.
sudo sh -c 'ulimit -c unlimited || echo "WARNING: Could not remove the PHP core dump limit" >&2; exec php --version'
./create_and_run_app_service.sh "php -S 0.0.0.0:5985"
echo "RUN AFTER THE SERVICE"
cat test-app.service
echo "RUN php DONE"
