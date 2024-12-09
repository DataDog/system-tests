#!/bin/bash

if [ -z "${WEBLOG_URL-}" ]; then
   WEBLOG_URL="http://localhost:18080"
fi

curl --fail --silent --show-error "${WEBLOG_URL}"
