#!/bin/bash
echo "START RUN APP"


sudo sed -i "s/18080/5985/g" index.js 
sudo cp index.js /home/datadog
sudo cp test-app-nodejs.service /etc/systemd/system/test-app-nodejs.service
sudo systemctl daemon-reload
sudo systemctl enable test-app-nodejs.service
sudo systemctl start test-app-nodejs.service
sudo systemctl status test-app-nodejs.service

echo "RUN DONE"