#!/bin/bash
echo "START RUN APP"

#Create folder for app logs
sudo mkdir -p /var/log/datadog_weblog
sudo chmod 777 /var/log/datadog_weblog

# Enable core dumps for host-app crashes (e.g. PHP + profiling segfaults).
# LimitCORE=infinity on test-app.service also applies once systemd starts the app.
ulimit -c unlimited || true
echo 1 | sudo tee /proc/sys/fs/suid_dumpable >/dev/null || true
echo "/var/log/datadog_weblog/core.%e.%p" | sudo tee /proc/sys/kernel/core_pattern >/dev/null || true

COMMAND_LINE=$1
APP_ENV="${2:-''}"

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

sed -i "s,APP_RUN_COMMAND,$COMMAND_LINE,g" test-app.service 
sudo cp test-app.service /etc/systemd/system/test-app.service
sudo systemctl daemon-reload
sudo systemctl enable test-app.service
sudo systemctl start test-app.service
sudo systemctl status test-app.service

echo "RUN DONE"