#!/bin/bash
echo "START nodejs APP"

sudo sed -i "s/18080/5985/g" index.js 
sudo cp index.js /home/datadog
sudo chmod 755 create_and_run_app_service.sh
./create_and_run_app_service.sh "node index.js"

echo "RUN nodejs DONE"