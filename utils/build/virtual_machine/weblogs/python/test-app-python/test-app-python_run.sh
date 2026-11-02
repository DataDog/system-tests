#!/bin/bash
echo "START python APP"

set -e

# Configure pyenv if it's installed (needed for some Python versions like 2.7)
if [ -d "/home/datadog/.pyenv" ]; then
  export PATH="/home/datadog/.pyenv/bin:$PATH" 
  eval "$(pyenv init -)"
fi

# shellcheck disable=SC2035
sudo chmod -R 755 * 

sudo cp django_app.py /home/datadog/
sudo cp pip.conf /etc/pip.conf
# Use the same pip3 that sudo will run. Ubuntu 23+ needs --break-system-packages.
# Some unsupported images ship Python without pip; those keep the previous skip.
if sudo pip3 install --help >/dev/null 2>&1; then
  if sudo pip3 install --help 2>/dev/null | grep -q -- '--break-system-packages'; then
    sudo pip3 install --break-system-packages django
  else
    sudo pip3 install django
  fi
else
  echo "pip3 is not installed; skipping Django install"
fi
./create_and_run_app_service.sh "python -m django runserver 0.0.0.0:5985" "PYTHONUNBUFFERED=1 DJANGO_SETTINGS_MODULE=django_app"
echo "RUN python DONE"
