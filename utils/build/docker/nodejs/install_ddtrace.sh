#!/bin/bash

set -eu

cd /usr/app

if [ -e /binaries/nodejs-load-from-npm ]; then
    target=$(</binaries/nodejs-load-from-npm)
    echo "install from: $target"

elif [ -e /binaries/dd-trace-js ]; then
    target=$(npm pack /binaries/dd-trace-js)
    echo "install from local folder /binaries/dd-trace-js"

else
    target="dd-trace"
    echo "install from NPM"
fi

npm install $target

npm list --json | jq -r '.dependencies."dd-trace".version' > SYSTEM_TESTS_LIBRARY_VERSION
npm explore @datadog/native-appsec -- cat package.json | jq -r '.libddwaf_version' > SYSTEM_TESTS_LIBDDWAF_VERSION
npm explore dd-trace -- cat packages/dd-trace/src/appsec/recommended.json | jq -r '.metadata.rules_version // "1.2.5"' > SYSTEM_TESTS_APPSEC_EVENT_RULES_VERSION

echo "dd-trace version: $(cat SYSTEM_TESTS_LIBRARY_VERSION)"
echo "libddwaf version: $(cat SYSTEM_TESTS_LIBDDWAF_VERSION)"
echo "rules version: $(cat SYSTEM_TESTS_APPSEC_EVENT_RULES_VERSION)"
