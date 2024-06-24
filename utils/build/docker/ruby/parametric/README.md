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
