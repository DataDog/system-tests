#!/bin/bash

DISTRO=$1

if [ "$DISTRO" = "deb" ]; then
   apt update -y
   apt install -y php
else
   yum install -y php
fi
