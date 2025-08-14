#!/bin/bash
echo "START python APP"

set -e

export PATH="/home/datadog/.pyenv/bin:$PATH"
eval "$(pyenv init -)"
# shellcheck disable=SC2035
sudo chmod -R 755 *

sudo cp django_app.py /home/datadog/

# Detect a suitable Python interpreter (prefer pyenv shims, then python3, then python)
PYTHON_BIN=""
if [ -x "/home/datadog/.pyenv/shims/python" ]; then
    PYTHON_BIN="/home/datadog/.pyenv/shims/python"
elif command -v python3 >/dev/null 2>&1; then
    PYTHON_BIN="$(command -v python3)"
elif command -v python >/dev/null 2>&1; then
    PYTHON_BIN="$(command -v python)"
else
    echo "No suitable python interpreter found (checked pyenv shims, python3, python)" >&2
    exit 1
fi

echo "Using python interpreter: $PYTHON_BIN"
sudo "$PYTHON_BIN" --version || true

# Ensure pip is available for the selected interpreter
if ! sudo -H "$PYTHON_BIN" -m pip --version >/dev/null 2>&1; then
    echo "Bootstrapping pip via ensurepip..."
    sudo -H "$PYTHON_BIN" -m ensurepip --upgrade || true
    sudo -H "$PYTHON_BIN" -m pip install --upgrade pip || true
fi

# Install a package with retries and sane defaults
pip_install_with_retries() {
    PACKAGE_NAME="$1"
    MAX_ATTEMPTS=5
    ATTEMPT=1
    while [ "$ATTEMPT" -le "$MAX_ATTEMPTS" ]; do
        echo "Installing $PACKAGE_NAME (attempt $ATTEMPT/$MAX_ATTEMPTS)"
        if sudo -H env PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_DEFAULT_TIMEOUT=60 "$PYTHON_BIN" -m pip install --no-cache-dir --timeout 60 --retries 5 "$PACKAGE_NAME"; then
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

./create_and_run_app_service.sh "$PYTHON_BIN -m django runserver 0.0.0.0:5985" "PYTHONUNBUFFERED=1 DJANGO_SETTINGS_MODULE=django_app"
echo "RUN python DONE"