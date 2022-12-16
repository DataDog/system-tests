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
- The test case creates a new span and sets a tag on it using the shared GRPC interface.
- Data is flushed to the test agent after the with test_library block closes.
- Data is retrieved using the `test_agent` fixture and asserted on.


## Usage


### Installation

The following dependencies are required to run the tests locally:

- Docker
- Python >= 3.7 (for Windows users, Python 3.9 seems to run best without issues)

then, create a Python virtual environment and install the Python dependencies:

```sh
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

```powershell
python -m venv venv
. .\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```


### Running the tests

Run all the tests:

```sh
./run.sh
```

```powershell
.\run.ps1
```

Run a specific test (`test_metrics_msgpack_serialization_TS001`) against multiple libraries (`dotnet`, `golang`):

```sh
CLIENTS_ENABLED=dotnet,golang,nodejs ./run.sh -k test_metrics_msgpack_serialization_TS001
```

```powershell
$env:CLIENTS_ENABLED="dotnet,golang,nodejs"
.\run.ps1 -k test_metrics_msgpack_serialization_TS001
```


Run all tests matching pattern

```sh
CLIENTS_ENABLED=dotnet,golang ./run.sh -k test_metrics_
```

```powershell
$env:CLIENTS_ENABLED="dotnet,golang"
.\run.ps1 -k test_metrics_
```


Run all tests from a file

```sh
CLIENTS_ENABLED=dotnet,golang ./run.sh test_span_sampling.py
```

```powershell
$env:CLIENTS_ENABLED="dotnet,golang"
.\run.ps1 test_span_sampling.py
```


Override skipped tests using `OVERRIDE_SKIPS`. This is useful when developing a feature
and the test has not been updated in this repo yet (but you want the test to run in the library CI).

```sh
CLIENTS_ENABLED=nodejs OVERRIDE_SKIPS=test_single_rule_match_span_sampling_sss001 ./run.sh test_span_sampling.py
```

```powershell
$env:CLIENTS_ENABLED="nodejs"
$env:OVERRIDE_SKIPS="test_single_rule_match_span_sampling_sss001"
.\run.ps1 test_span_sampling.py
```


Tests can be aborted using CTRL-C but note that containers maybe still be running and will have to be shut down.

#### Go

For running the Go tests, see the README in apps/golang.

To test unmerged PRs locally, run the following in the apps/golang directory:

```sh
go get -u gopkg.in/DataDog/dd-trace-go.v1@<commit_hash>
go mod tidy
```


#### Python

To run the Python tests "locally" push your code to a branch and then specify ``PYTHON_DDTRACE_PACKAGE``.


```sh
PYTHON_DDTRACE_PACKAGE=git+https://github.com/Datadog/dd-trace-py@1.x ./run.sh ...
```


### Debugging

The stdout and stderr logs of the test run will include the output from the library server and the test agent container.
These can be used to debug the test case.

The output also contains the commands used to build and run the containers which can be run manually to debug the issue
further.


## Troubleshooting

- Ensure docker is running.
- Exiting the tests abruptly maybe leave some docker containers running. Use `docker ps` to find and `docker kill` any
  containers that may still be running.


### Port conflict on 50052

If there is a port conflict with an existing process on the local machine then the default port `50052` can be
overridden using `APM_GRPC_SERVER_PORT=... ./run.sh`.


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



## Implementation

### Shared Interface

In order to achieve shared tests, we introduce a shared GRPC interface to the clients. Thus, each client need only implement the GRPC interface server and then these shared tests can be run against the library. The GRPC interface implements common APIs across the clients which provide the building blocks for test cases.

```proto
service APMClient {
  rpc StartSpan(StartSpanArgs) returns (StartSpanReturn) {}
  rpc FinishSpan(FinishSpanArgs) returns (FinishSpanReturn) {}
  rpc SpanSetMeta(SpanSetMetaArgs) returns (SpanSetMetaReturn) {}
  rpc SpanSetMetric(SpanSetMetricArgs) returns (SpanSetMetricReturn) {}
  rpc FlushSpans(FlushSpansArgs) returns (FlushSpansReturn) {}
  rpc FlushTraceStats(FlushTraceStatsArgs) returns (FlushTraceStatsReturn) {}
}
```

### Architecture

- Shared tests are written in Python (pytest).
- GRPC servers for each language are built and run in docker containers.
- [test agent](https://github.com/DataDog/dd-apm-test-agent/) is started in a container to collect the data from the GRPC servers. 

Test cases are written in Python and target the shared GRPC interface. The tests use a GRPC client to query the servers and the servers generate the data which is submitted to the test agent. Test cases can then query the data from the test agent to perform assertions.


<img width="869" alt="image" src="https://user-images.githubusercontent.com/6321485/182887064-e241d65c-5e29-451b-a8a8-e8d18328c083.png">
