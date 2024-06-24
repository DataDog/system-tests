#!/bin/bash
echo "START RUN APP"

# shellcheck disable=SC2035
sudo chmod -R 755 *

DD_INSTRUMENT_SERVICE_WITH_APM=false bundle install

# shellcheck disable=SC2035
sudo cp -R * /home/datadog

# shellcheck disable=SC2035
sudo chmod -R 755 /home/datadog

sudo chown -R datadog:datadog /home/datadog
#Ubuntu work without this, but Amazon Linux needs bundle install executed with datadog user
sudo su - datadog -c 'DD_INSTRUMENT_SERVICE_WITH_APM=false bundle install'
sudo cp test-app.service /etc/systemd/system/test-app.service
sudo systemctl daemon-reload
sudo systemctl enable test-app.service
sudo systemctl start test-app.service
sudo systemctl status test-app.service

#TODO Extract the output file in other step
sleep 5
sudo cat /home/datadog/app-std.out

echo "RUN DONE"
