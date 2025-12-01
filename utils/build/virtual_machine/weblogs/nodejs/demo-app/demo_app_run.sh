#!/bin/bash

# shellcheck disable=SC2028

sudo chmod +x create_and_run_app_service.sh 
echo 'while true; do { echo -e "HTTP/1.1 200 OK\nContent-Length: 5\n\nHola"; } | nc -l -p 5985; done' > socket_listener.sh
sudo chmod +x socket_listener.sh
sudo cp socket_listener.sh /usr/bin
 ./create_and_run_app_service.sh "socket_listener.sh"