#!/bin/bash
echo "START RUN APP"

 
#This is the output for the app service
sudo touch /home/datadog/app-std.out
sudo chmod 777 /home/datadog/app-std.out
sudo rm Gemfile.lock
sudo sed -i "s/3.1.3/>= 3.0.0\", \"< 3.3.0/g" Gemfile || sed -i "s/3.1.3/>= 3.0.0\", \"< 3.3.0/g" Gemfile
export DD_INSTRUMENT_SERVICE_WITH_APM=false 
sudo bundle install
export DD_INSTRUMENT_SERVICE_WITH_APM=true
# shellcheck disable=SC2035
sudo cp -R * /home/datadog
sudo chmod -R 755 /home/datadog
sudo chown -R datadog:datadog /home/datadog
sudo cp test-app.service /etc/systemd/system/test-app.service
sudo systemctl daemon-reload
sudo systemctl enable test-app.service
sudo systemctl start test-app.service
sudo systemctl status test-app.service

sleep 5
cat /home/datadog/app-std.out

echo "RUN DONE"