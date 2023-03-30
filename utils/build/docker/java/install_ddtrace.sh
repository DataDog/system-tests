#!/bin/bash

set -eu

if [ $(ls /dd-java-agent*.jar | wc -l) = 1 ]; then
    echo "Install local file $(ls /dd-java-agent*.jar)"
    [ ! -f "dd-java-agent.jar"  ] && cp $(ls /dd-java-agent*.jar) /dd-java-agent.jar  
else
    echo "Too many jar files in binaries"
    exit 1
fi

if [ $(ls /LIBRARY_VERSION | wc -l) = 0 ]; then
  java -jar /dd-java-agent.jar > /LIBRARY_VERSION
  touch /LIBDDWAF_VERSION
  LIBRARY_VERSION=$(cat /LIBRARY_VERSION)
  if [[ $LIBRARY_VERSION == 0.96* ]]; then
    echo "1.2.5" > /APPSEC_EVENT_RULES_VERSION
  else
    bsdtar -O - -xf /dd-java-agent.jar appsec/default_config.json | \
      grep rules_version | head -1 | awk -F'"' '{print $4;}' \
      > /APPSEC_EVENT_RULES_VERSION
  fi
fi

echo "dd-trace version: $(cat /LIBRARY_VERSION)"
echo "libddwaf version: $(cat /LIBDDWAF_VERSION)"
echo "rules version: $(cat /APPSEC_EVENT_RULES_VERSION)"

