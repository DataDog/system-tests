#!/bin/bash
echo "START RUN APP"

sudo sed -i "s/3.1.3/3.0.2/g" Gemfile 
sudo DD_INSTRUMENT_SERVICE_WITH_APM=false bundle install
sudo cp -R * /home/datadog
sudo chmod -R 755 /home/datadog
sudo chown -R datadog:datadog /home/datadog
sudo cp test-app-ruby.service /etc/systemd/system/test-app-ruby.service
sudo systemctl daemon-reload
sudo systemctl enable test-app-ruby.service
sudo systemctl start test-app-ruby.service
sudo systemctl status test-app-ruby.service

echo "RUN DONE"