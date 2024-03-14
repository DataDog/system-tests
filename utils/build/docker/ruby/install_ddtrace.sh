#!/bin/bash

set -eu

sed -i -e '/gem .datadog./d' Gemfile
if [ -e "/binaries/dd-trace-rb" ]; then
    # ddtrace is loaded from a local folder
    # look inside this folder to find the version (2.x or 1.x)
    echo "Install from folder /binaries/dd-trace-rb"
    echo "gem 'datadog', require: 'datadog/auto_instrument', path: '/binaries/dd-trace-rb'" >> Gemfile
elif [ $(ls /binaries/ruby-load-from-bundle-add | wc -l) = 0 ]; then
    echo "Install prod version"

    # last releases version
    # is there a way to know if this version is 1.x or 2.x? probably hard to do ? 

    # IF it's 2.x, then
    echo "gem 'datadog', require: 'datadog/auto_instrument'" >> Gemfile
    # ELSE
    echo "gem 'ddtrace', require: 'datadog/auto_instrument'" >> Gemfile
    # FI
else
    # open thee content of the file /binaries/ruby-load-from-bundle-add
    # and append this content to gemfile
    # SO:
    # if this content contains ddtrace, it's 1.x
    # otherwise, it's 2.x

    # for instance, if the content of this file is : 

    # `gem 'ddtrace', git: "https://github.com/Datadog/dd-trace-rb", branch: "master", require: 'ddtrace/auto_instrument'`

    # there is ddtrace inside it => it's 1.x

    
    options=$(cat /binaries/ruby-load-from-bundle-add)
    echo "Install from $options"
    echo $options >> Gemfile
fi

# here, we are supposed to know if it's 1.x or 2.x
# if it's 1.x
# search and replace 'datadog' by 'ddtrace' in this list of file : 
# * utils/build/docker/ruby/parametric/Gemfile
# * utils/build/docker/ruby/rack/config.ru


bundle config set --local without test development
bundle remove ddtrace
bundle update datadog

bundle info datadog | grep -m 1 datadog > SYSTEM_TESTS_LIBRARY_VERSION
bundle list | grep libddwaf > SYSTEM_TESTS_LIBDDWAF_VERSION || true

cat "$(bundle info datadog | grep 'Path:' | awk '{ print $2 }')"/lib/datadog/appsec/assets/waf_rules/recommended.json | ruby -rjson -e 'puts JSON.parse(STDIN.read).fetch("metadata", {}).fetch("rules_version", "1.2.5")' > SYSTEM_TESTS_APPSEC_EVENT_RULES_VERSION


echo "dd-trace version: $(cat SYSTEM_TESTS_LIBRARY_VERSION)"
echo "libddwaf version: $(cat SYSTEM_TESTS_LIBDDWAF_VERSION)"
echo "appsec event rules version: $(cat SYSTEM_TESTS_APPSEC_EVENT_RULES_VERSION)"
