#!/bin/bash

ruby -rbundler/setup -e 'puts Gem::Specification.find_all.find {|x| x.name == "ddtrace" || x.name == "datadog"}.version'
