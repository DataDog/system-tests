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

### Running the tests

Build will happen at the beginning of the run statements.

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

### Using Pytest

The tests are executed using pytest. Below are some common command-line options you can use to control and customize your test runs.
- `-k EXPRESSION`: Run tests that match the given expression (substring or pattern). Useful for running specific tests or groups of tests.

```sh
TEST_LIBRARY=dotnet ./run.sh PARAMETRIC -k test_metrics_msgpack_serialization_TS001
```

- `-v`: Increase verbosity. Shows each test name and its result (pass/fail) as they are run.

```sh
TEST_LIBRARY=dotnet ./run.sh PARAMETRIC -v
```

- `-vv`: Even more verbose output. Provides detailed information including setup and teardown for each test.

```sh
TEST_LIBRARY=dotnet ./run.sh PARAMETRIC -vv -k test_metrics_
```

- `-s`: Disable output capture. Allows you to see print statements and logs directly in the console.

```sh
TEST_LIBRARY=dotnet ./run.sh PARAMETRIC -s
```

### Running the tests for a custom tracer

#### Go

To test unmerged PRs locally, run the following in the utils/build/docker/golang/parametric directory:

```sh
go get -u gopkg.in/DataDog/dd-trace-go.v1@<commit_hash>
go mod tidy
```

#### dotnet

- Add a file `datadog-dotnet-apm-<VERSION>.tar.gz` in `binaries/`. `<VERSION>` must be a valid version number.
  - One way to get that file is from an Azure pipeline (either a recent one from master if the changes you want to test were merged recently, or the one from your PR if it's open)

#### Java

Follow these steps to run Parametric tests with a custom Java Tracer version:

1. Clone the repo and checkout to the branch you'd like to test:
```bash
git clone git@github.com:DataDog/dd-trace-java.git
cd dd-trace-java
```
By default you will be on the `master` branch, but if you'd like to run system-tests on the changes you made to your local branch, `git checkout` to that branch before proceeding.

2. Build Java Tracer artifacts
```
./gradlew :dd-java-agent:shadowJar :dd-trace-api:jar
```

3. Copy both artifacts into the `system-tests/binaries/` folder:
  * The Java tracer agent artifact `dd-java-agent-*.jar` from `dd-java-agent/build/libs/`
  * Its public API `dd-trace-api-*.jar` from `dd-trace-api/build/libs/` into

Note, you should have only TWO jar files in `system-tests/binaries`. Do NOT copy sources or javadoc jars.

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

To run the Python tests against a custom tracer:
```bash
echo “ddtrace @ git+https://github.com/DataDog/dd-trace-py.git@<name-of-your-branch>” > binaries/python-load-from-pip
```

#### NodeJS

There are three ways for running the NodeJS tests with a custom tracer:
1. Create a file `nodejs-load-from-npm` in `binaries/`, the content will be installed by `npm install`. Content example:
    - `DataDog/dd-trace-js#master`
2. Clone the dd-trace-js repo inside `binaries`
3. Create a file `nodejs-load-from-local` in `binaries/`, this will disable installing with `npm install dd-trace` and
   will instead get the content of the file, and use it as a location of the `dd-trace-js` repo and then mount it as a
   volume and `npm link` to it. For instance, if this repo is at the location, you can set the content of this file to
   `../dd-trace-js`. This also removes the need to rebuild the weblog image since the code is mounted at runtime.

#### Ruby

There is two ways for running the Ruby tests with a custom tracer:

1. Create an file ruby-load-from-bundle-add in binaries/, the content will be installed by bundle add. Content example:
gem 'datadog', git: "https://github.com/Datadog/dd-trace-rb", branch: "master", require: 'datadog/auto_instrument'
2. Clone the dd-trace-rb repo inside binaries

#### C++

There is two ways for running the C++ library tests with a custom tracer:
1. Create a file `cpp-load-from-git` in `binaries/`. Content examples:
    * `https://github.com/DataDog/dd-trace-cpp@main`
    * `https://github.com/DataDog/dd-trace-cpp@<COMMIT HASH>`
2. Clone the dd-trace-cpp repo inside `binaries`

#### When you are done testing against a custom tracer:
```bash
rm -rf binaries/python-load-from-pip
```

### Understanding the test outcomes
Please refer to this chart:

| Declaration            | Test is executed  | Test actual outcome | System test output  | Comment
| -                      | -                 | -                   | -                   | -
| \<no_declaration>      | Yes               | ✅ Pass             | 🟢 Success          | All good :sunglasses:
| Missing feature or bug | Yes               | ❌ Fail             | 🟢 Success          | Expected failure
| Missing feature or bug | Yes               | ✅ Pass             | 🟠 Success          | XPASS: The feature has been implemented, bug has been fixed -> easy win
| Flaky                  | No                | N.A.                | N.A.                | A flaky test doesn't provide any usefull information, and thus, is not executed.
| Irrelevant             | No                | N.A.                | N.A                 | There is no purpose of running such a test
| \<no_declaration>      | Yes               | ❌ Fail             | 🔴 Fail             | Only use case where system test fails : the test should have been ok, and is not

### Debugging

The stdout and stderr logs of the test run will include the output from the library server and the test agent container.
These can be used to debug the test case.

The output also contains the commands used to build and run the containers which can be run manually to debug the issue
further.

The logs are contained in this folder:  `./logs_parametric`

## Troubleshooting

- Ensure docker is running.
- Ensure you do not have a datadog agent running outside the tests (`ps aux | grep 'datadog'` can help you check this).
- Exiting the tests abruptly maybe leave some docker containers running. Use `docker ps` to find and `docker kill` any
  containers that may still be running.

### Tests failing locally but not in CI

A cause for this can be that the Docker image containing the APM library is cached locally with an older version of the
library. Deleting the image will force a rebuild which will resolve the issue.

```sh
docker image rm <library>-test-library
```

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

### Docker Cleanup
If you encounter an excessive number of errors during your workflow, one potential solution is to perform a cleanup of Docker resources. This can help resolve issues related to corrupted containers, dangling images, or unused volumes that might be causing conflicts.

```sh
docker system prune
```

**⚠️ Warning:**
Executing `docker system prune` will remove all stopped containers, unused networks, dangling images, and build caches. This action is **irreversible** and may result in the loss of important data. Ensure that you **do not** need any of these resources before proceeding.

## Developing the tests

### Extending the interface

The Python implementation of the interface `app/python`, when run, provides a specification of the API when run.
See the steps below in the HTTP section to run the Python server and view the specification.

### Shared Interface

#### HTTP

We have transitioned to using an HTTP interface, replacing the legacy GRPC interface. To view the available HTTP endpoints , follow these steps:

1. ```
./utils/scripts/parametric/run_reference_http.sh
```

2. Navigate to http://localhost:8000/docs in your web browser to access the documentation.

3. You can download the OpenAPI schema from http://localhost:8000/openapi.json. This schema can be imported into tools like [Postman](https://learning.postman.com/docs/integrations/available-integrations/working-with-openAPI/) or other API clients to facilitate development and testing.

#### Legacy GRPC
**Important:** The legacy GRPC interface will be **deprecated** and no longer in use. All client interactions and tests will be migrated to use the HTTP interface.

Previously, we used a shared GRPC interface to enable shared testing across different clients. Each client would implement the GRPC interface server, allowing shared tests to be run against the client libraries. The GRPC service definition included methods like StartSpan, FinishSpan, SpanSetMeta, and others, which facilitated span and trace operations.

#### Updating protos for GRPC (will be deprecated)

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

### Architecture/How System-tests work
Below is an overview of how the  testing architecture is structured:
- Shared Tests in Python: We write shared test cases using Python's pytest framework. These tests are designed to be generic and interact with clients through the HTTP interface.
- HTTP Servers in Docker: For each language client, we build and run an HTTP server within a Docker container. These servers expose the required endpoints defined in the OpenAPI schema and handle the client-specific logic.
- [Test Agent](https://github.com/DataDog/dd-apm-test-agent/) in Docker: We start a test agent in a separate Docker container. This agent collects data (such as spans and traces) submitted by the HTTP servers. It serves as a centralized point for aggregating and accessing test data.
- Test Execution: The Python test cases use an HTTP client to communicate with the servers. The servers generate data based on the interactions, which is then sent to the test agent. The tests can query the test agent to retrieve  data and perform assertions to verify correct behavior.

This architecture allows us to ensure that all clients conform to the same interface and behavior, making it easier to maintain consistency across different languages and implementations.

<img width="869" alt="image" src="https://user-images.githubusercontent.com/6321485/182887064-e241d65c-5e29-451b-a8a8-e8d18328c083.png">

[1]: https://github.com/DataDog/dd-trace-cpp
[2]: https://docs.pytest.org/en/6.2.x/usage.html#specifying-tests-selecting-tests
[3]: https://github.com/roydahan/xunit-viewer
[4]: ../../utils/build/docker/cpp/parametric/CMakeLists.txt
