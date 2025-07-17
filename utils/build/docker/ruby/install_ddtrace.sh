#!/bin/bash

set -eu

if [ -e "/binaries/dd-trace-rb" ]; then
    #
    # Build the gem from the local directory
    # And use it in weblog gemfile
    # This way, it will go through compilation steps of the native lib
    # and will be closer an actual installation.
    #
    echo "Build and install gem from /binaries/dd-trace-rb"

    # Remove gem reference from Gemfile
    sed -i -e '/gem .datadog./d' Gemfile

    cat Gemfile

    # Read the gem name and version from the gemspec file
    export GEM_NAME=$(find /binaries/dd-trace-rb -name *.gemspec | ruby -ne 'puts Gem::Specification.load($_.chomp).name')
    export GEM_VERSION=$(find /binaries/dd-trace-rb -name *.gemspec | ruby -ne 'puts Gem::Specification.load($_.chomp).version')

    # if gem -v is >= 4.0 (including 5.0, 12.0...), use gem -C PATH build, else use gem build -C PATH
    if gem -v | ruby -ne 'exit(Gem::Version.new($_.chomp) >= Gem::Version.new("4.0") ? 0 : 1)'; then
        gem -C /binaries/dd-trace-rb build
    else
        gem build -C /binaries/dd-trace-rb
    fi
    gem install /binaries/dd-trace-rb/$GEM_NAME-*.gem

    echo -e "gem '$GEM_NAME', '$GEM_VERSION', require: '$GEM_NAME/auto_instrument'" >> Gemfile

    bundle install
elif [ $(ls /binaries/ruby-load-from-bundle-add | wc -l) = 0 ]; then
    # nothing to do - the Gemfile should already point to the latest released version
    bundle update datadog
else
    # Remove gem reference from Gemfile
    sed -i -e '/gem .datadog./d' Gemfile

    #
    # Append the content of the file `/binaries/ruby-load-from-bundle-add``
    # to the Gemfile to install the gem of any configuration. Please allows maximum flexibility.
    #
    # Example of content:
    # `gem 'datadog', git: "https://github.com/Datadog/dd-trace-rb", branch: "master", require: 'ddtrace/auto_instrument'`
    #
    options=$(cat /binaries/ruby-load-from-bundle-add)
    echo "Install from $options"
    echo $options >> Gemfile

    # Read the gem name from the Gemfile
    export GEM_NAME=$(ruby -rbundler -e 'puts Bundler::Definition.build("Gemfile", nil, nil).dependencies.find {|x| x.name == "ddtrace" || x.name == "datadog"}.name')

    bundle install
fi
