#!/bin/bash
echo "START RUN APP"

#Create folder for app logs
sudo mkdir /var/log/weblog
sudo chmod 777 /var/log/weblog

COMMAND_LINE=$1
sed -i "s,APP_RUN_COMMAND,$COMMAND_LINE,g" test-app.service 
sudo cp test-app.service /etc/systemd/system/test-app.service
sudo systemctl daemon-reload
sudo systemctl enable test-app.service
sudo systemctl start test-app.service
sudo systemctl status test-app.service

echo "RUN DONE"