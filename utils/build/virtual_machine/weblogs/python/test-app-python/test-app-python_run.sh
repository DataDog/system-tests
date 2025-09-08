#!/bin/bash
echo "START python APP"

set -e

export PATH="/home/datadog/.pyenv/bin:$PATH" 
eval "$(pyenv init -)"
# shellcheck disable=SC2035
sudo chmod -R 755 * 

sudo cp django_app.py /home/datadog/
sudo pip3 install django==5.2.4 || true
./create_and_run_app_service.sh "python -m django runserver 0.0.0.0:5985" "PYTHONUNBUFFERED=1 DJANGO_SETTINGS_MODULE=django_app"
echo "RUN python DONE"