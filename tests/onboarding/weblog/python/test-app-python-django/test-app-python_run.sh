#!/bin/bash
echo "START RUN APP"

set -e
sudo chmod -R 755 *

sudo cp django_app.py /home/datadog/
sudo /home/datadog/.pyenv/shims/pip3 install django
echo "Testing weblog with python version:"
sudo /home/datadog/.pyenv/shims/python --version
sudo cp test-app-python.service /etc/systemd/system/test-app-python.service
sudo systemctl daemon-reload
sudo systemctl enable test-app-python.service
sudo systemctl start test-app-python.service
sudo systemctl status test-app-python.service

echo "RUN DONE"