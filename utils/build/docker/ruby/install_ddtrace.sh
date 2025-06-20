#!/bin/bash

set -eu

# Remove gem reference from Gemfile
sed -i -e '/gem .ddtrace./d' Gemfile
sed -i -e '/gem .datadog./d' Gemfile

cat Gemfile

if [ -e "/binaries/dd-trace-rb-null" ]; then
    #
    # Build the gem from the local directory
    # And use it in weblog gemfile
    # This way, it will go through compilation steps of the native lib
    # and will be closer an actual installation.
    #
    echo "Build and install gem from /binaries/dd-trace-rb"

    # Read the gem name and version from the gemspec file
    export GEM_NAME=$(find /binaries/dd-trace-rb -name *.gemspec | ruby -ne 'puts Gem::Specification.load($_.chomp).name')
    export GEM_VERSION=$(find /binaries/dd-trace-rb -name *.gemspec | ruby -ne 'puts Gem::Specification.load($_.chomp).version')

    gem -C /binaries/dd-trace-rb build
    gem install /binaries/dd-trace-rb/$GEM_NAME-*.gem

    echo -e "gem '$GEM_NAME', '$GEM_VERSION', require: '$GEM_NAME/auto_instrument'" >> Gemfile
elif [ $(ls /binaries/ruby-load-from-bundle-add | wc -l) = 0 ]; then
    #
    # Install the gem from https://rubygems.org/
    # This means the gem is already released and publicly available
    #
    echo "Install prod version"
    # Support multiple versions of the gem
    echo "gem 'datadog', '>= 2.0.0.beta2', require: 'datadog/auto_instrument'" >> Gemfile

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
