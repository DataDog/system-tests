# Rules

We add new weblog **only** when it makes sense. For instance, when it's a next major
release or an important breaking change that is so significant, that it must be
addressed as a separate weblog.

In every major release, we try to keep the most recent patch version of the framework,
with a caveat covered in previous sentence.

Otherwise, please use `dd-trace-rb` repository tests to cover a specific permutation.

The Ruby version must be the most recent version of the major release, unless it's
a specific version is required by the framework.

# Permutations

Some weblogs contain additional enpoints and gem versions that are not present in
other weblogs. For instance, Rails 7.2 has `/otel_drop_in_default_propagator_extract`
and `/kafka/` endpoints.

Rails 7.2
* `/otel_drop_in_default_propagator_extract` with `opentelemetry-{sdk,api}` gem
* `/otel_drop_in_default_propagator_inject` with `opentelemetry-{sdk,api}` gem
* `/read_file`
* `/log/library`
* `/kafka/*` with `ruby-kafka` gem
* `/debugger/*`

Rails 8.0
* `/kafka/*` with `rdkafka` gem
* `/debugger/*`

# Updating Gemfile.lock

In order to update the lockfile, we use the following commands inside the container:

1. To update the lockfile to the most recent version of the framework, run:
    ```bash
    $ bundle lock --update
    ```
2. To add the target platform to the lockfile, run one of the following commands:
    ```bash
    $ bundle lock --add-platform x86_64-linux-gnu
    $ bundle lock --add-platform arm64-darwin
    $ bundle lock --add-platform aarch64-linux-gnu
    $ bundle lock --add-platform x86_64-darwin
    ```

The ruby version is specified in the `Dockerfile` file. And to run the commands,
you need to be inside the container, like this:

```bash
$ cd utils/build/docker/ruby/rails72
$ docker run --rm -it -v "${PWD}":"${PWD}" -w "${PWD}" ghcr.io/datadog/images-rb/engines/ruby:3.2 bash
```

## Ruby 2.5 tips & tricks

For Ruby 2.5 and Rails 4.2 we need to use bundler < 2.

```bash
$ docker run --rm -it -v "${PWD}":"${PWD}" -w "${PWD}" ghcr.io/datadog/images-rb/engines/ruby:2.5 bash
$ root@c262f9bc5bd8: gem install -N bundler:1.17.3
$ root@c262f9bc5bd8: rm $(ruby -e 'puts Gem.default_specifications_dir')/bundler-2.*.gemspec
```