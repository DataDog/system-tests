#!/bin/bash
echo "START RUN APP"
tar xvf test-app-python.tar


pip3 install django
echo "Testing weblog with python version:"
python --version
sudo sed -i "s/MY_USER/$(whoami)/g" test-app-python.service 
sudo cp test-app-python.service /etc/systemd/system/test-app-python.service
sudo systemctl daemon-reload
sudo systemctl enable test-app-python.service
sudo systemctl start test-app-python.service
sudo systemctl status test-app-python.service

echo "RUN DONE"