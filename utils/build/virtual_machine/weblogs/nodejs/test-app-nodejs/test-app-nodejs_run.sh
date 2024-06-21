#!/bin/bash
echo "START RUN APP"

#Create folder for app logs
sudo mkdir /var/log/test-app
sudo chmod 777 /var/log/test-app

sudo sed -i "s/18080/5985/g" index.js 
sudo cp index.js /home/datadog
sudo cp test-app.service /etc/systemd/system/test-app.service
sudo systemctl daemon-reload
sudo systemctl enable test-app.service
sudo systemctl start test-app.service
sudo systemctl status test-app.service
sleep 5
cat /home/datadog/app-std.out

echo "RUN DONE"