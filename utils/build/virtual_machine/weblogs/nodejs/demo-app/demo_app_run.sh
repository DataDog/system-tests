#!/bin/bash

# shellcheck disable=SC2028
if command -v apt &>/dev/null; then
    sudo apt update && sudo apt install -y netcat
elif command -v yum &>/dev/null; then
    sudo yum install -y nc
elif command -v dnf &>/dev/null; then
    sudo dnf install -y nc
elif command -v zypper &>/dev/null; then
    sudo zypper install -y netcat
else
    echo "Unsupported package manager. Install Netcat manually."
    exit 1
fi

sudo chmod +x create_and_run_app_service.sh 
echo 'while true; do { echo -e "HTTP/1.1 200 OK\nContent-Length: 5\n\nHola"; } | nc -l -p 5985; done' > socket_listener.sh
sudo chmod +x socket_listener.sh
sudo cp socket_listener.sh /usr/bin
 ./create_and_run_app_service.sh "socket_listener.sh"