#!/bin/bash

set -eu

# Remove gem reference from Gemfile
sed -i -e '/gem .ddtrace./d' Gemfile
sed -i -e '/gem .datadog./d' Gemfile

cat Gemfile

if [ -e "/binaries/dd-trace-rb" ]; then
    #
    # Install the gem from this local directory
    # Being triggered by upstream: https://github.com/DataDog/dd-trace-rb
    #
    echo "Install from folder /binaries/dd-trace-rb"

    # Read the gem name from the gemspec file
    export GEM_NAME=$(find /binaries/dd-trace-rb -name *.gemspec | ruby -ne 'puts Gem::Specification.load($_.chomp).name')

    echo "gem '$GEM_NAME', require: '$GEM_NAME/auto_instrument', path: '/binaries/dd-trace-rb'" >> Gemfile
elif [ $(ls /binaries/ruby-load-from-bundle-add | wc -l) = 0 ]; then
    #
    # Install the gem from https://rubygems.org/
    # This means the gem is already released and publicly available
    #
    echo "Install prod version"
    # Support multiple versions of the gem
    echo "gem 'datadog' ~> '~> 2.0.0.beta2'" >> Gemfile

    export GEM_NAME=datadog
else
    #
    # Append the content of the file `/binaries/ruby-load-from-bundle-add``
    # to the Gemfile to install the gem of any configuration. Please allows maximum flexibility.
    #
    # Example of content:
    # `gem 'ddtrace', git: "https://github.com/Datadog/dd-trace-rb", branch: "master", require: 'ddtrace/auto_instrument'`
    #
    options=$(cat /binaries/ruby-load-from-bundle-add)
    echo "Install from $options"
    echo $options >> Gemfile

    # Read the gem name from the Gemfile
    export GEM_NAME=$(ruby -rbundler -e 'puts Bundler::Definition.build("Gemfile", nil, nil).dependencies.find {|x| x.name == "ddtrace" || x.name == "datadog"}.name')
fi

bundle config set --local without test development

bundle install

bundle info $GEM_NAME | grep -m 1 $GEM_NAME > SYSTEM_TESTS_LIBRARY_VERSION
bundle list | grep libddwaf > SYSTEM_TESTS_LIBDDWAF_VERSION || true

cat "$(bundle info $GEM_NAME | grep 'Path:' | awk '{ print $2 }')"/lib/datadog/appsec/assets/waf_rules/recommended.json | ruby -rjson -e 'puts JSON.parse(STDIN.read).fetch("metadata", {}).fetch("rules_version", "1.2.5")' > SYSTEM_TESTS_APPSEC_EVENT_RULES_VERSION

echo "dd-trace version: $(cat SYSTEM_TESTS_LIBRARY_VERSION)"
echo "libddwaf version: $(cat SYSTEM_TESTS_LIBDDWAF_VERSION)"
echo "appsec event rules version: $(cat SYSTEM_TESTS_APPSEC_EVENT_RULES_VERSION)"
