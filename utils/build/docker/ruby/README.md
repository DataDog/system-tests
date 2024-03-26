# System test apps for Ruby

## Updating lockfiles


```
# example with rails71

# get base image to use same ruby version
cat rails71.Dockerfile | perl -ne '/^FROM (.*)/ and print "$1\n"'

# go into app
cd rails71

# conservative lock update (like bundle install)
docker run --rm -it -v "${PWD}":"${PWD}" -w "${PWD}" ghcr.io/datadog/dd-trace-rb/ruby:3.2.0-dd bundle lock

# full lock update (like bundle update)
docker run --rm -it -v "${PWD}":"${PWD}" -w "${PWD}" ghcr.io/datadog/dd-trace-rb/ruby:3.2.0-dd bundle lock --update

# adding a target platform with same deps as local platform
docker run --rm -it -v "${PWD}":"${PWD}" -w "${PWD}" ghcr.io/datadog/dd-trace-rb/ruby:3.2.0-dd bundle lock --add-platform x86_64-linux-gnu
docker run --rm -it -v "${PWD}":"${PWD}" -w "${PWD}" ghcr.io/datadog/dd-trace-rb/ruby:3.2.0-dd bundle lock --add-platform aarch64-linux-gnu
docker run --rm -it -v "${PWD}":"${PWD}" -w "${PWD}" ghcr.io/datadog/dd-trace-rb/ruby:3.2.0-dd bundle lock --add-platform x86_64-darwin
docker run --rm -it -v "${PWD}":"${PWD}" -w "${PWD}" ghcr.io/datadog/dd-trace-rb/ruby:3.2.0-dd bundle lock --add-platform arm64-darwin
```
