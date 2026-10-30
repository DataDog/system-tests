#!/bin/bash

ruby -rbundler/setup <<EOF
    gemspec = Gem.loaded_specs['datadog'] || Gem.loaded_specs['ddtrace']
    puts gemspec.version.to_s
EOF
