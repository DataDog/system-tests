#!/bin/bash
echo "START RUN APP"

if ! command -v systemctl &> /dev/null
then
    sed -i "s/18080/5985/g" index.js 
    cp index.js /home/datadog
    chmod 777 /shared_volume/std.out
    chmod 755 test-app-nodejs_daemon.sh
    ./test-app-nodejs_daemon.sh start
 else
    sudo sed -i "s/18080/5985/g" index.js 
    sudo cp index.js /home/datadog
    sudo cp test-app.service /etc/systemd/system/test-app.service
    sudo systemctl daemon-reload
    sudo systemctl enable test-app.service
    sudo systemctl start test-app.service
    sudo systemctl status test-app.service
fi

echo "RUN DONE"