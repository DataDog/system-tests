#!/bin/bash
echo "START RUN APP"

curl -L https://github.com/wildfly/wildfly/releases/download/27.0.1.Final/wildfly-27.0.1.Final.tar.gz --output wildfly-27.0.1.Final.tar.gz 
tar -xf wildfly-27.0.1.Final.tar.gz 

sudo sed -i "s/MY_USER/$(whoami)/g" wildfly.service 
sudo cp wildfly.service /etc/systemd/system/wildfly.service
sudo systemctl daemon-reload
sudo systemctl enable wildfly.service
sudo systemctl start wildfly.service
sudo systemctl status wildfly.service

echo "RUN DONE"