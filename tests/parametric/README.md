# APM library parametric tests

The tests in this submodule target a shared interface so that **all** the APM libraries can be tested with a single test case.

This enables us to write unit/integration-style test cases that can be shared.

Example:

```python
@parametrize("library_env", [{"DD_ENV": "prod"}, {"DD_ENV": "dev"}])
def test_tracer_env_environment_variable(library_env, test_library, test_agent):
  with test_library:
    with test_library.start_span("operation"):
      pass

  traces = test_agent.traces()
  trace = find_trace_by_root(traces, Span(name="operation"))
  assert len(trace) == 1

  span = find_span(trace, Span(name="operation"))
  assert span["name"] == "operation"
  assert span["meta"]["env"] == library_env["DD_ENV"]
```

- This test case runs against all the APM libraries and is parameterized with two different environments specifying two different values of the environment variable `DD_ENV`.
- The test case creates a new span and sets a tag on it using the shared GRPC/HTTP interface.
- Data is flushed to the test agent after the with test_library block closes.
- Data is retrieved using the `test_agent` fixture and asserted on.


## Usage


### Installation

Make sure you're in the `root` directory before running these commands.

The following dependencies are required to run the tests locally:

- Docker
- Python >= 3.7 (for Windows users, Python 3.9 seems to run best without issues)

then, run the following command, which will create a Python virtual environment and install the Python dependencies from the root directory:

```sh
./build.sh -i runner
```


### Running the tests

Run all the tests:

```sh
./run.sh PARAMETRIC
```

Run a specific test (`test_metrics_msgpack_serialization_TS001`):

```sh
TEST_LIBRARY=dotnet ./run.sh PARAMETRIC -k test_metrics_msgpack_serialization_TS001
```

Run all tests matching pattern

```sh
TEST_LIBRARY=dotnet ./run.sh PARAMETRIC -k test_metrics_
```

Tests can be aborted using CTRL-C but note that containers maybe still be running and will have to be shut down.

#### Go

For running the Go tests, see the README in apps/golang.

To test unmerged PRs locally, run the following in the apps/golang directory:

```sh
go get -u gopkg.in/DataDog/dd-trace-go.v1@<commit_hash>
go mod tidy
```

#### dotnet

To test unmerged PRs locally, do the following:
- In your local dd-trace-dotnet repo, build the `Datadog.Trace` NuGet package. The easiest way to do this is to run `dotnet pack` from the `/tracer/src/Datadog.Trace` directory.
- Copy the resulting `.nupkg` file into the `apps/dotnet` directory
- In `apps/dotnet/ApmTestClient.csproj`, update the version of the `Datadog.Trace` package reference to the dev version

#### Java

##### Run Parametric tests with a custom Java Tracer version

1. Build Java Tracer artifacts
```bash
git clone git@github.com:DataDog/dd-trace-java.git
cd dd-trace-java
./gradlew :dd-java-agent:shadowJar :dd-trace-api:jar
```

2. Copy both artifacts into the `system-tests/binaries/` folder:
  * The Java tracer agent artifact `dd-java-agent-*.jar` from `dd-java-agent/build/libs/`
  * Its public API `dd-trace-api-*.jar` from `dd-trace-api/build/libs/` into

3. Run Parametric tests from the `system-tests/parametric` folder:

```bash
CLIENTS_ENABLED=java ./run.sh test_span_sampling.py::test_single_rule_match_span_sampling_sss001
```


#### PHP

If you are seeing DNS resolution issues when running the tests locally, add the following config to the Docker daemon:

```json
  "dns-opts": [
    "single-request"
  ],
```


#### Python

To run the Python tests "locally" push your code to a branch and then specify ``PYTHON_DDTRACE_PACKAGE``.


```sh
PYTHON_DDTRACE_PACKAGE=git+https://github.com/Datadog/dd-trace-py@1.x ./run.sh ...
```

#### NodeJS

There is two ways for running the NodeJS tests with a custom tracer:
- Place the ddtrace NPM package in the folder ``apps/nodejs/npm`` and then set the environment variable ``NODEJS_DDTRACE_MODULE``
with the filename placed in the aforementioned folder. For example:
``CLIENTS_ENABLED=nodejs NODEJS_DDTRACE_MODULE="dd-trace-2.22.3.tgz" ./run.sh``
- Set the environment variable ``NODEJS_DDTRACE_MODULE`` to hold a commit in a remote branch. The following example will run
the tests with a specific commit: ``CLIENTS_ENABLED=nodejs NODEJS_DDTRACE_MODULE=datadog/dd-trace-js#687cb813289e19bfcc884a2f9f634470cf138143 ./run.sh``

#### Ruby

To run the Ruby tests "locally" push your code GitHub and then specify `RUBY_DDTRACE_SHA`:

```sh
RUBY_DDTRACE_SHA=0552ebd49dc5b3bec4e739c2c74b214fb3102c2a ./run.sh ...
```

#### C++

The parametric shared tests can be run against the C++ library,
[dd-trace-cpp][1], this way:
```console
$ TEST_LIBRARY=cpp ./run.sh PARAMETRIC
```

Use the `-k` command line argument, which is forwarded to [pytest][2], to
specify a substring within a particular test file, class, or method. Then only
matching tests will run, e.g.
```console
$ TEST_LIBRARY=cpp ./run.sh PARAMETRIC -k test_headers
```

It's convenient to have a pretty printer for the tests' XML output. I use
[xunit-viewer][3].
```console
$ npm install junit-viewer -g
```

My development iterations then involve running the following at the top of the
repository:
```console
$ TEST_LIBRARY=cpp ./run.sh PARAMETRIC -k test_headers; xunit-viewer -r logs_parametric/reportJunit.xml
```

This will create a file `index.html` at the top of the repository, which I then
inspect with a web browser.

The C++ build can be made to point to a different GitHub branch by modifying the
`FetchContent_Declare` command's `GIT_TAG` argument in [CMakeLists.txt][4].

In order to coerce Docker to rebuild the C++ gRPC server image, one of the build
inputs must change, and so whenever I push changes to the target branch, I also
modify a scratch comment in `CMakeLists.txt` to trigger a rebuild on the next
test run.

### Debugging

The stdout and stderr logs of the test run will include the output from the library server and the test agent container.
These can be used to debug the test case.

The output also contains the commands used to build and run the containers which can be run manually to debug the issue
further.


## Troubleshooting

- Ensure docker is running.
- Ensure you do not have a datadog agent running outside the tests (`ps aux | grep 'datadog'` can help you check this).
- Exiting the tests abruptly maybe leave some docker containers running. Use `docker ps` to find and `docker kill` any
  containers that may still be running.


### Port conflict on 50052

If there is a port conflict with an existing process on the local machine then the default port `50052` can be
overridden using `APM_LIBRARY_SERVER_PORT`.


### Disable build kit

If logs like

```
Failed to fire hook: while creating logrus local file hook: user: Current requires cgo or $USER, $HOME set in environment
[2023-01-04T21:44:49.583965000Z][docker-credential-desktop][F] get system info: exec: "sw_vers": executable file not found in $PATH
[goroutine 1 [running, locked to thread]:
[common/pkg/system.init.0()
[	common/pkg/system/os_info.go:32 +0x1bc
#3 ERROR: rpc error: code = Unknown desc = error getting credentials - err: exit status 1, out: ``
```

are being produced then likely build kit has to be disabled.

To do that open the Docker UI > Docker Engine. Change `buildkit: true` to `buildkit: false` and restart Docker.


### Tests failing locally but not in CI

A cause for this can be that the Docker image containing the APM library is cached locally with an older version of the
library. Deleting the image will force a rebuild which will resolve the issue.

```sh
docker image rm <library>-test-library
```


## Developing the tests

### Extending the interface

The Python implementation of the interface `app/python_http`, when run, provides a specification of the API when run.
See the steps below in the HTTP section to run the Python server and view the specification.

## Implementation

### Shared Interface

#### GRPC

In order to achieve shared tests, we introduce a shared GRPC interface to the clients. Thus, each client need only implement the GRPC interface server and then these shared tests can be run against the library. The GRPC interface implements common APIs across the clients which provide the building blocks for test cases.

```proto
service APMClient {
  rpc StartSpan(StartSpanArgs) returns (StartSpanReturn) {}
  rpc FinishSpan(FinishSpanArgs) returns (FinishSpanReturn) {}
  rpc SpanSetMeta(SpanSetMetaArgs) returns (SpanSetMetaReturn) {}
  rpc SpanSetMetric(SpanSetMetricArgs) returns (SpanSetMetricReturn) {}
  rpc SpanSetError(SpanSetErrorArgs) returns (SpanSetErrorReturn) {}
  rpc InjectHeaders(InjectHeadersArgs) returns (InjectHeadersReturn) {}
  rpc FlushSpans(FlushSpansArgs) returns (FlushSpansReturn) {}
  rpc FlushTraceStats(FlushTraceStatsArgs) returns (FlushTraceStatsReturn) {}
  rpc StopTracer(StopTracerArgs) returns (StopTracerReturn) {}
}
```

#### HTTP

An HTTP interface can be used instead of the GRPC. To view the interface run

```
PORT=8000 ./run_reference_http.sh
```

and navigate to http://localhost:8000. The OpenAPI schema can be downloaded at
http://localhost:8000/openapi.json. The schema can be imported
into [Postman](https://learning.postman.com/docs/integrations/available-integrations/working-with-openAPI/) or
other tooling to assist in development.


### Architecture

- Shared tests are written in Python (pytest).
- GRPC/HTTP servers for each language are built and run in docker containers.
- [test agent](https://github.com/DataDog/dd-apm-test-agent/) is started in a container to collect the data from the GRPC servers.

Test cases are written in Python and target the shared GRPC interface. The tests use a GRPC client to query the servers and the servers generate the data which is submitted to the test agent. Test cases can then query the data from the test agent to perform assertions.


<img width="869" alt="image" src="https://user-images.githubusercontent.com/6321485/182887064-e241d65c-5e29-451b-a8a8-e8d18328c083.png">

[1]: https://github.com/DataDog/dd-trace-cpp
[2]: https://docs.pytest.org/en/6.2.x/usage.html#specifying-tests-selecting-tests
[3]: https://github.com/roydahan/xunit-viewer
[4]: ../../utils/build/docker/cpp/parametric/CMakeLists.txt
