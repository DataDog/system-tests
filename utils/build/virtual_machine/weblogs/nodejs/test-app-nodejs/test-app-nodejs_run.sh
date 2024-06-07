#!/bin/bash
echo "START RUN APP"

sudo sed -i "s/18080/5985/g" index.js 
sudo cp index.js /home/datadog

#This is the output for the app service
sudo touch /home/datadog/app-std.out
sudo chmod 777 /home/datadog/app-std.out

sudo cp test-app.service /etc/systemd/system/test-app.service
sudo systemctl daemon-reload
sudo systemctl enable test-app.service
sudo systemctl start test-app.service
sudo systemctl status test-app.service
sleep 5
cat /home/datadog/app-std.out

echo "RUN DONE"