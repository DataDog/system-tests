#!/bin/bash

ruby -rbundler/setup <<EOF
    gemspec = Gem.loaded_specs['datadog'] || Gem.loaded_specs['ddtrace']
    version = gemspec.version.to_s
    # Only append -dev if not from RubyGems AND version doesn't already have a prerelease component
    if !gemspec.source.is_a?(Bundler::Source::Rubygems) && !gemspec.version.prerelease?
      version = "#{version}-dev"
    end
    puts version
EOF
