#!/bin/bash

DISTRO=$1

if [ "$DISTRO" = "deb" ]; then
   apt update -y
   apt install -y php
else
   echo "Installing PHP"
   yum install -y php
   echo "Installing PHP JSON"
   yum install -y php-json
fi
