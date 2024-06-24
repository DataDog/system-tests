#!/bin/bash
echo "START python APP"

set -e

# shellcheck disable=SC2035
sudo chmod -R 755 * 

sudo cp django_app.py /home/datadog/
sudo /home/datadog/.pyenv/shims/pip3 install django
echo "Testing weblog with python version:"
sudo /home/datadog/.pyenv/shims/python --version
./create_and_run_app_service.sh "/home/datadog/.pyenv/shims/python -m django runserver 0.0.0.0:5985"
echo "RUN AFTER THE SERVICE"
cat test-app.service
echo "RUN python DONE"