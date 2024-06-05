#!/bin/bash
echo "START RUN APP"

set -e

# shellcheck disable=SC2035
sudo chmod -R 755 * || chmod -R 755 *


if ! command -v systemctl &> /dev/null
then
    cp django_app.py /home/datadog/
    /home/datadog/.pyenv/shims/pip3 install django
    echo "Testing weblog with python version:"
    /home/datadog/.pyenv/shims/python --version
    chmod 755 test-app-python_daemon.sh
    chmod 777 /shared_volume/std.out
    ./test-app-python_daemon.sh start
 else
    sudo cp django_app.py /home/datadog/
    sudo /home/datadog/.pyenv/shims/pip3 install django
    echo "Testing weblog with python version:"
    sudo /home/datadog/.pyenv/shims/python --version
    sudo cp test-app.service /etc/systemd/system/test-app.service
    sudo systemctl daemon-reload
    sudo systemctl enable test-app.service
    sudo systemctl start test-app.service
    sudo systemctl status test-app.service
fi

echo "RUN DONE"