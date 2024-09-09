#!/bin/bash

set -e

declare -r RUNTIME_VERSIONS="$1"

curl -s "https://get.sdkman.io" | bash
# shellcheck source=/dev/null
source "/root/.sdkman/bin/sdkman-init.sh"
sed -i -e 's/sdkman_auto_answer=false/sdkman_auto_answer=true/g' /root/.sdkman/etc/config

for VERSION in $(echo "$RUNTIME_VERSIONS" | tr ',' ' '); do
    sdk install java "$VERSION"
done

#ln -s "${SDKMAN_DIR}/candidates/java/current" java
ln -s "${SDKMAN_DIR}/candidates/java/current/bin/java" /usr/bin/java
ln -s "${SDKMAN_DIR}/candidates/java/current/bin/javac" /usr/bin/javac