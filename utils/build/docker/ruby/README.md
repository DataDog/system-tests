# System test apps for Ruby

TODO: Write a better readme

## Updating lockfiles

### Ruby 2.5 bundler issue

``` text
$ docker run --rm -it -v "${PWD}":"${PWD}" -w "${PWD}" ghcr.io/datadog/images-rb/engines/ruby:2.5 bash
$ root@c262f9bc5bd8: gem install -N bundler:1.17.3
$ root@c262f9bc5bd8: rm $(ruby -e 'puts Gem.default_specifications_dir')/bundler-2.*.gemspec
```

# example with rails71

# get base image to use same ruby version
cat rails71.Dockerfile | perl -ne '/^FROM (.*)/ and print "$1\n"'

# go into app
cd rails71

# conservative lock update (like bundle install)
docker run --rm -it -v "${PWD}":"${PWD}" -w "${PWD}" ghcr.io/datadog/images-rb/engines/ruby:3.2 bundle lock

# full lock update (like bundle update)
docker run --rm -it -v "${PWD}":"${PWD}" -w "${PWD}" ghcr.io/datadog/images-rb/engines/ruby:3.2 bundle lock --update

# adding a target platform with same deps as local platform
docker run --rm -it -v "${PWD}":"${PWD}" -w "${PWD}" ghcr.io/datadog/images-rb/engines/ruby:3.2 bundle lock --add-platform x86_64-linux-gnu
docker run --rm -it -v "${PWD}":"${PWD}" -w "${PWD}" ghcr.io/datadog/images-rb/engines/ruby:3.2 bundle lock --add-platform aarch64-linux-gnu
docker run --rm -it -v "${PWD}":"${PWD}" -w "${PWD}" ghcr.io/datadog/images-rb/engines/ruby:3.2 bundle lock --add-platform x86_64-darwin
docker run --rm -it -v "${PWD}":"${PWD}" -w "${PWD}" ghcr.io/datadog/images-rb/engines/ruby:3.2 bundle lock --add-platform arm64-darwin
```
