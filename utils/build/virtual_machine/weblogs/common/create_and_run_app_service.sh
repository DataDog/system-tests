#!/bin/bash
echo "START RUN APP"

#Create folder for app logs
sudo mkdir /var/log/datadog_weblog
sudo chmod 777 /var/log/datadog_weblog

COMMAND_LINE=$1
APP_ENV="${2:-''}"
STOP_COMMAND_LINE="${3:-''}"
#ENV variables set on the scenario definition
SCENARIO_APP_ENV="${DD_APP_ENV:-''}"

echo "$APP_ENV" | tr '[:space:]' '\n' > /var/log/datadog_weblog/app.env
sudo chmod 777 /var/log/datadog_weblog/app.env

echo "$SCENARIO_APP_ENV" | tr '[:space:]' '\n' > /var/log/datadog_weblog/scenario_app.env
sudo chmod 777 /var/log/datadog_weblog/scenario_app.env

echo "Using app environment variables:"
cat /var/log/datadog_weblog/app.env

echo "Using scenario app environment variables:"
cat /var/log/datadog_weblog/scenario_app.env

if [ -d "/etc/systemd/" ]; then
    sed -i "s,APP_RUN_COMMAND,$COMMAND_LINE,g" test-app.service 
    sudo cp test-app.service /etc/systemd/system/test-app.service 
    sudo systemctl daemon-reload
    sudo systemctl enable test-app.service
    sudo systemctl start test-app.service
    sudo systemctl status test-app.service
else
    sed -i "s,APP_RUN_COMMAND,$COMMAND_LINE,g" test-app.sysvinit
    sed -i "s,APP_STOP_COMMAND,$STOP_COMMAND_LINE,g" test-app.sysvinit
    sudo cp test-app.sysvinit /etc/init.d/test-app.service
    sudo service test-app.service start
fi


echo "RUN DONE"