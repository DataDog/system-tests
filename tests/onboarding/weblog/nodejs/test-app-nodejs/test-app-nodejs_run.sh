#!/bin/bash
echo "START RUN APP"


sudo sed -i "s/18080/5985/g" index.js 
sudo cp index.js /home/datadog
sudo cp test-app.service /etc/systemd/system/test-app.service
sudo systemctl daemon-reload
sudo systemctl enable test-app.service
sudo systemctl start test-app.service
sudo systemctl status test-app.service

echo "RUN DONE"