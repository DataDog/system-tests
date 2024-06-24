#!/bin/bash
echo "START RUN APP"

#Create folder for app logs
sudo mkdir /var/log/weblog
sudo chmod 777 /var/log/weblog

sudo sed -i "s/18080/5985/g" index.js 
sudo cp index.js /home/datadog
sudo cp test-app.service /etc/systemd/system/test-app.service
sudo systemctl daemon-reload
sudo systemctl enable test-app.service
sudo systemctl start test-app.service
sudo systemctl status test-app.service
sleep 5
cat /var/log/weblog/app.log

echo "RUN DONE"