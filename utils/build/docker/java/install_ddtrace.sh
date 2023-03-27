#!/bin/bash

set -eu


echo "Install local file $(ls /dd-java-agent*.jar)"
mv /dd-java-agent*.jar /dd-java-agent.jar
java -jar /dd-java-agent.jar > /LIBRARY_VERSION

echo "Installed $(cat /LIBRARY_VERSION) java library"

touch /LIBDDWAF_VERSION

LIBRARY_VERSION=$(cat /LIBRARY_VERSION)

if [[ $LIBRARY_VERSION == 0.96* ]]; then
  echo "1.2.5" > /APPSEC_EVENT_RULES_VERSION
else
  bsdtar -O - -xf /dd-java-agent.jar appsec/default_config.json | \
    grep rules_version | head -1 | awk -F'"' '{print $4;}' \
    > /APPSEC_EVENT_RULES_VERSION
fi

echo "dd-trace version: $(cat /LIBRARY_VERSION)"
echo "libddwaf version: $(cat /LIBDDWAF_VERSION)"
echo "rules version: $(cat /APPSEC_EVENT_RULES_VERSION)"
