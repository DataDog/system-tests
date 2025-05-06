# Running all tests

From the `/parametric` directory (`cd ../..` from this file's location), run:
```sh
CLIENTS_ENABLED=ruby ./run.sh
```

To run a single test file:
```sh
CLIENTS_ENABLED=ruby ./run.sh test_headers_b3.py
```

To run a single test:
```sh
CLIENTS_ENABLED=ruby ./run.sh -k test_metrics_msgpack_serialization_TS001
```

To run with a specific `datadog` version, push your code to GitHub and then specify `RUBY_DDTRACE_SHA`:

```sh
RUBY_DDTRACE_SHA=0552ebd49dc5b3bec4e739c2c74b214fb3102c2a ./run.sh ...
```

# Debugging the Ruby server

The server runs on Ruby 3.2.1.

To debug the server locally, run:
```sh
bundle install
./generate_proto.sh
DEBUG=1 bundle exec ruby server.rb
```

You'll be presented with a Ruby REPL, with the gRPC server running in the same process.

A `client` object will be available for you to make gRPC requests to the server.

# Locally run Parametric system-tests with an unreleased version of libdatadog

This is a bit of a hack that is intended to help you validate WIP changes in dd-trace-rb while waiting for libdatadog release.

1. Clone and compile `libdatadog`, and move it to dd-trace-rb folder
    ```
    export DD_RUBY_PLATFORM=`ruby -e 'puts Gem::Platform.local.to_s'`
    mkdir -p compiled_libdatadog_folder/$DD_RUBY_PLATFORM
    ./build-profiling-ffi.sh compiled_libdatadog_folder/$DD_RUBY_PLATFORM
    mv compiled_libdatadog_folder /path/to/dd-trace-rb/tmp
    ```

2. Add `ENV["LIBDATADOG_VENDOR_OVERRIDE"] ||= Pathname.new("#{__dir__}/../tmp/compiled_libdatadog_folder/").expand_path.to_s`to dd-trace-rb's `ext/libdatadog_extconf_helpers.rb`

3. Add compile step in parametric tests Dockerfile template located in `utils/_context/_scenarios/parametric.py::ruby_library_factory`
    - Change the FROM line to `ghcr.io/datadog/images-rb/engines/ruby:3.2` (or any Ruby version that you've used during the `libdatadog` compile step)
    - After `COPY {ruby_reldir}/../install_ddtrace.sh binaries* /binaries/` line, add:
    ```
    WORKDIR /binaries/dd-trace-rb
    RUN bundle install
    # Replace with your Ruby version and platform
    RUN bundle exec rake clean compile:libdatadog_api.3.2_aarch64-linux
    # Or if you want to compile profiling too
    # RUN bundle exec rake clean compile
    WORKDIR /app
    ```

4. In `utils/build/docker/install_ddtrace.sh`, replace the last `bundle install` by `bundle install --force --gemfile=Gemfile`
    - For whatever reason, this `bundle install` will reuse dd-trace-rb's one instead of the app one if you don't specify the Gemfile.
