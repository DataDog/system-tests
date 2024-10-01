#!/bin/bash

DISTRO=$1

if [ "$DISTRO" = "deb" ]; then
   apt update -y
   apt install -y php
elif [ "$DISTRO" = "amazon_linux_2" ]; then
   amazon-linux-extras install -y php8.2
else
   echo "Installing PHP"
   yum install -y php
   echo "Installing PHP JSON"
   yum install -y php-json
fi
