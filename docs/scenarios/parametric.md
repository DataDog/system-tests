# APM library parametric tests

The tests in this submodule target a shared interface so that **all** the APM libraries can be tested with a single test case.

This enables us to write unit/integration-style test cases that can be shared.

Example:

```python
from utils.parametric.spec.trace import find_span, find_trace, find_span_in_traces, find_first_span_in_trace_payload, find_root_span

@pytest.mark.parametrize("library_env", [{"DD_ENV": "prod"}])
def test_datadog_spans(library_env, test_library, test_agent):
    with test_library:
        with test_library.start_span("operation") as s1:
            with test_library.start_span("operation1", service="hello", parent_id=s1.span_id) as s2:
                pass

        with test_library.start_span("otel_rocks") as os1:
            pass

    # Waits for 2 traces to be captured and avoids sorting the received spans by start time
    # Here we want to perserve the order of spans to easily access the chunk root span (first span in payload)
    traces = test_agent.wait_for_num_traces(2, sort_by_start=False)
    assert len(traces) == 2, traces

    trace1 = find_trace(traces, s1.trace_id)
    assert len(trace1) == 2

    span1 = find_span(trace1, s1.span_id)
    # Ensure span1 is the root span of trace1
    assert span1 == find_root_span(trace1)
    assert span1["name"] == "operation"

    span2 = find_span(trace1, s2.span_id)
    assert span2["name"] == "operation1"
    assert span2["service"] == "hello"

    # Chunk root span can be span1 or span2 depending on how the trace was serialized
    # This span will contain trace level tags (ex: _dd.p.tid)
    first_span = find_first_span_in_trace_payload(trace1)
    # Make sure trace level tags exist on the chunk root span
    assert "language" in first_span["meta"]
    assert first_span["meta"]["env"] == "prod"

    # Get one span from the list of captured traces
    ospan = find_span_in_traces(traces, os1.trace_id, os1.span_id)
    assert ospan["resource"] == "otel_rocks"
    assert ospan["meta"]["env"] == "prod"
```

- This test case runs against all the APM libraries and is parameterized with two different environments specifying two different values of the environment variable `DD_ENV`.
- The test case creates a new span and sets a tag on it using the shared GRPC/HTTP interface.
- The implementations of the GRPC/HTTP interface, by language, are in `utils/build/docker/<lang>/parametric`.
- Data is flushed to the test agent after the with test_library block closes.
- Data is retrieved using the `test_agent` fixture and asserted on.


## Usage


### Installation

Make sure you're in the root of the repository before running these commands.

The following dependencies are required to run the tests locally:

- Docker
- Python 3.12

then, run the following command, which will create a Python virtual environment and install the Python dependencies from the root directory:

```sh
./build.sh -i runner
```


### Running the tests

Run all the tests for a particular tracer library:

```sh
TEST_LIBRARY=dotnet ./run.sh PARAMETRIC
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

To test unmerged PRs locally, run the following in the utils/build/docker/golang/parametric directory:

```sh
go get -u gopkg.in/DataDog/dd-trace-go.v1@<commit_hash>
go mod tidy
```

#### dotnet

Add a file datadog-dotnet-apm-<VERSION>.tar.gz in binaries/. <VERSION> must be a valid version number.

#### Java

##### Run Parametric tests with a custom Java Tracer version

1. Clone the repo and checkout to the branch you'd like to test
Clone the repo:
```bash
git clone git@github.com:DataDog/dd-trace-java.git
cd dd-trace-java
```
By default you will be on the `master` branch, but if you'd like to run system-tests on the changes you made to your local branch, `git checkout` to that branch before proceeding.

2. Build Java Tracer artifacts
```
./gradlew :dd-java-agent:shadowJar :dd-trace-api:jar
```

3. You should now have a Java tracer agent artifact called `dd-java-agent-*.jar` under the `dd-trace-java/dd-java-agent/build/libs/` folder and a Java tracer public API artifact called `dd-trace-api-*.jar` under the `dd-trace-java/dd-trace-api/build/libs/` folder (Note: the * is a placeholder for the version snapshot you built locally, so the files won't literally be called e.g,`dd-java-agent-*.jar`). Move these files into the system tests repo under its `/binaries` folder: `system-tests/binaries/`.

*Note*, you should have only TWO jar files in `system-tests/binaries`. Do NOT copy sources or javadoc jars.

4. Run Parametric tests from the `system-tests/parametric` folder:

```bash
TEST_LIBRARY=java ./run.sh test_span_sampling.py::test_single_rule_match_span_sampling_sss001
```


#### PHP

##### To run with a custom build

- Place `datadog-setup.php` and `dd-library-php-[X.Y.Z+commitsha]-aarch64-linux-gnu.tar.gz` (or the `x86_64` if you're not on ARM) in `/binaries` folder
  - You can download those from the `build_packages/package extension` job artifacts, from a CI run of your branch.
- Copy it in the binaries folder

##### Then run the tests

From the repo root folder:

- `./build.sh -i runner`
- `TEST_LIBRARY=php ./run.sh PARAMETRIC` or `TEST_LIBRARY=php ./run.sh PARAMETRIC -k <my_test>`

> :warning: **If you are seeing DNS resolution issues when running the tests locally**, add the following config to the Docker daemon:

```json
  "dns-opts": [
    "single-request"
  ],
```


#### Python

To run the Python tests "locally" push your code to a branch and then specify ``PYTHON_DDTRACE_PACKAGE``.


```sh
TEST_LIBRARY=python PYTHON_DDTRACE_PACKAGE=git+https://github.com/Datadog/dd-trace-py@2.x ./run.sh PARAMETRIC [-k ...]
```

#### NodeJS

There is three ways for running the NodeJS tests with a custom tracer:
1. Create a file `nodejs-load-from-npm` in `binaries/`, the content will be installed by `npm install`. Content example:
    * `DataDog/dd-trace-js#master`
2. Clone the dd-trace-js repo inside `binaries`
3. Create a file `nodejs-load-from-local` in `binaries/`, this will disable installing with `npm install dd-trace` and
   will instead get the content of the file, and use it as a location of the `dd-trace-js` repo and then mount it as a
   volume and `npm link` to it. For instance, if this repo is at the location, you can set the content of this file to
   `../dd-trace-js`. This also removes the need to rebuild the weblog image since the code is mounted at runtime.

#### Ruby

There is two ways for running the Ruby tests with a custom tracer:

1. Create an file ruby-load-from-bundle-add in binaries/, the content will be installed by bundle add. Content example:
gem 'ddtrace', git: "https://github.com/Datadog/dd-trace-rb", branch: "master", require: 'ddtrace/auto_instrument'
In addition, instead of `branch:`, `ref` can be used to reference a commit hash.
We'd recommend this if you're going to be iterating as it causes the build
script to always rebuild the ddtrace gem.
2. Clone the dd-trace-rb repo inside binaries

#### C++

There is two ways for running the C++ library tests with a custom tracer:
1. Create a file `cpp-load-from-git` in `binaries/`. Content examples:
    * `https://github.com/DataDog/dd-trace-cpp@main`
    * `https://github.com/DataDog/dd-trace-cpp@<COMMIT HASH>`
2. Clone the dd-trace-cpp repo inside `binaries`

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

The Python implementation of the interface `app/python`, when run, provides a specification of the API when run.
See the steps below in the HTTP section to run the Python server and view the specification.

## Updating protos

In order to update the `parametric/protos`, these steps must be followed.

1. Create a virtual environment and activate it:
```bash
python3.12 -m venv .venv && source .venv/bin/activate
```

2. Install the required dependencies:
```bash
pip install -r requirements.txt
```

3. Install `grpcio-tools` (make sure grpcaio is the same version):
```bash
pip install grpcio-tools==1.60.1
```

4. Change directory to `utils/parametric`:
```console
cd utils/parametric
```

5. Run the script to generate the proto files:
```bash
./generate_protos.sh
```

Then you should have updated proto files. This script will generate weird files, you can ignore/delete these.

## Implementation

### Shared Interface

#### HTTP

An HTTP interface can be used instead of the GRPC. To view the interface run

```
./utils/scripts/parametric/run_reference_http.sh
```

and navigate to http://localhost:8000/docs. The OpenAPI schema can be downloaded at
http://localhost:8000/openapi.json. The schema can be imported
into [Postman](https://learning.postman.com/docs/integrations/available-integrations/working-with-openAPI/) or
other tooling to assist in development.


#### Legacy GRPC

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
