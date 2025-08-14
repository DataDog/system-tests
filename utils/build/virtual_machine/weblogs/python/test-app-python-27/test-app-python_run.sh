#!/bin/bash
echo "START python APP"

set -e

# shellcheck disable=SC2035
sudo chmod -R 755 *

sudo cp django_app.py /home/datadog/

PYTHON_BIN="/home/datadog/.pyenv/shims/python"
PIP_BIN="/home/datadog/.pyenv/shims/pip"

if [ ! -x "$PYTHON_BIN" ]; then
    echo "Expected pyenv shim python not found at $PYTHON_BIN" >&2
    exit 1
fi

echo "Testing weblog with python version:"
sudo "$PYTHON_BIN" --version || true

if ! sudo -H "$PIP_BIN" --version >/dev/null 2>&1; then
    echo "pip shim not found at $PIP_BIN" >&2
    exit 1
fi

pip_install_with_retries() {
    PACKAGE_NAME="$1"
    MAX_ATTEMPTS=5
    ATTEMPT=1
    while [ "$ATTEMPT" -le "$MAX_ATTEMPTS" ]; do
        echo "Installing $PACKAGE_NAME (attempt $ATTEMPT/$MAX_ATTEMPTS)"
        if sudo -H env PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_DEFAULT_TIMEOUT=60 "$PIP_BIN" install --no-cache-dir --timeout 60 --retries 5 "$PACKAGE_NAME"; then
            return 0
        fi
        SLEEP_TIME=$(( ATTEMPT * 5 ))
        echo "Install failed (attempt $ATTEMPT). Retrying in ${SLEEP_TIME}s..."
        sleep "$SLEEP_TIME"
        ATTEMPT=$(( ATTEMPT + 1 ))
    done
    echo "ERROR: Failed to install $PACKAGE_NAME after $MAX_ATTEMPTS attempts" >&2
    return 1
}

pip_install_with_retries django

./create_and_run_app_service.sh "$PYTHON_BIN -m django runserver 0.0.0.0:5985" "PYTHONPATH=/home/datadog/:$PYTHONPATH PYTHONUNBUFFERED=1 DJANGO_SETTINGS_MODULE=django_app"
echo "RUN AFTER THE SERVICE"
cat test-app.service
echo "RUN python DONE"
