#!/bin/bash

ruby -rbundler/setup <<EOF
    gemspec = Gem.loaded_specs['datadog'] || Gem.loaded_specs['ddtrace']
    version = gemspec.version.to_s
    version = "#{version}-dev" unless gemspec.source.is_a?(Bundler::Source::Rubygems)
    puts version
EOF
