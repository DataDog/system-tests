#!/bin/bash
echo "START RUN APP"

set -e

# shellcheck disable=SC2015
sudo chmod -R 755 *

sudo cp django_app.py /home/datadog/
sudo /home/datadog/.pyenv/shims/pip3 install django
echo "Testing weblog with python version:"
sudo /home/datadog/.pyenv/shims/python --version
sudo cp test-app.service /etc/systemd/system/test-app.service
sudo systemctl daemon-reload
sudo systemctl enable test-app.service
sudo systemctl start test-app.service
sudo systemctl status test-app.service

echo "RUN DONE"