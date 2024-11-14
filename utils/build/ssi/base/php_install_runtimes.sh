#!/bin/bash

curl -s "https://get.sdkman.io" | bash
# shellcheck source=/dev/null
source "/root/.sdkman/bin/sdkman-init.sh"
sed -i -e 's/sdkman_auto_answer=false/sdkman_auto_answer=true/g' /root/.sdkman/etc/config

sdk install java "11.0.24-zulu"


ln -s "${SDKMAN_DIR}/candidates/java/current/bin/java" /usr/bin/java
ln -s "${SDKMAN_DIR}/candidates/java/current/bin/javac" /usr/bin/javac
