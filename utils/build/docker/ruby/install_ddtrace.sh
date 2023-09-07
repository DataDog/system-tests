#!/bin/bash

set -eu

sed -i -e '/gem .ddtrace./d' Gemfile
if [ -e "/binaries/dd-trace-rb" ]; then
    echo "Install from folder /binaries/dd-trace-rb"
    echo "gem 'ddtrace', require: 'ddtrace/auto_instrument', path: '/binaries/dd-trace-rb'" >> Gemfile
elif [ $(ls /binaries/ruby-load-from-bundle-add | wc -l) = 0 ]; then
    echo "Install prod version"
    echo "gem 'ddtrace', require: 'ddtrace/auto_instrument'" >> Gemfile
else
    options=$(cat /binaries/ruby-load-from-bundle-add)
    echo "Install from $options"
    echo $options >> Gemfile
fi

bundle config set --local without test development
bundle update ddtrace

bundle list | grep ddtrace > SYSTEM_TESTS_LIBRARY_VERSION
bundle list | grep libddwaf > SYSTEM_TESTS_LIBDDWAF_VERSION || true

cat "$(bundle info ddtrace | grep 'Path:' | awk '{ print $2 }')"/lib/datadog/appsec/assets/waf_rules/recommended.json | ruby -rjson -e 'puts JSON.parse(STDIN.read).fetch("metadata", {}).fetch("rules_version", "1.2.5")' > SYSTEM_TESTS_APPSEC_EVENT_RULES_VERSION


echo "dd-trace version: $(cat SYSTEM_TESTS_LIBRARY_VERSION)"
echo "libddwaf version: $(cat SYSTEM_TESTS_LIBDDWAF_VERSION)"
echo "appsec event rules version: $(cat SYSTEM_TESTS_APPSEC_EVENT_RULES_VERSION)"
