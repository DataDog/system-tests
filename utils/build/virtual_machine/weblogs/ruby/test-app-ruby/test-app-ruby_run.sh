#!/bin/bash
echo "START RUN APP"
# shellcheck disable=SC2035


if ! command -v systemctl &> /dev/null
then
    rm Gemfile.lock || true
    sed -i "s/3.1.3/>= 3.0.0\", \"< 3.3.0/g" Gemfile
    DD_INSTRUMENT_SERVICE_WITH_APM=false bundle install  
    cp -R * /home/datadog
    chmod -R 755 /home/datadog
    chown -R datadog:datadog /home/datadog
    chmod 755 test-app-ruby_daemon.sh
    chmod 777 /shared_volume/std.out
    ./test-app-ruby_daemon.sh start
 else
    sudo sed -i "s/3.1.3/>= 3.0.0\", \"< 3.3.0/g" Gemfile
    sudo DD_INSTRUMENT_SERVICE_WITH_APM=false bundle install
    sudo cp -R * /home/datadog
    sudo chmod -R 755 /home/datadog
    sudo chown -R datadog:datadog /home/datadog
    sudo cp test-app.service /etc/systemd/system/test-app.service
    sudo systemctl daemon-reload
    sudo systemctl enable test-app.service
    sudo systemctl start test-app.service
    sudo systemctl status test-app.service
fi



echo "RUN DONE"