#!/bin/bash
echo "START RUN APP"

# shellcheck disable=SC2035
sudo chmod -R 755 *

sed -i "s/3.1.3/>= 3.0.0\", \"< 3.3.0/g" Gemfile
rm -rf Gemfile.lock
DD_INSTRUMENT_SERVICE_WITH_APM=false bundle install
#Fix amazon linux 2023
cp Gemfile.lock datadog-Gemfile.lock
# shellcheck disable=SC2035
sudo cp -R * /home/datadog

# shellcheck disable=SC2035
sudo chmod -R 755 /home/datadog

sudo chown -R datadog:datadog /home/datadog
sudo cp test-app.service /etc/systemd/system/test-app.service
sudo systemctl daemon-reload
sudo systemctl enable test-app.service
sudo systemctl start test-app.service
sudo systemctl status test-app.service

sleep 5
sudo cat /home/datadog/app-std.out

echo "RUN DONE"