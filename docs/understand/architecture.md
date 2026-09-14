# Overview

The components that make up a running test are simple from the outside.

The idea behind system tests is that we can share the tests for a given feature across implementations.

Enabling a feature within system tests might go like this:
 1. [Run the system test suite](#running-the-system-tests)
 1. Inspect `./logs/interfaces` folders to see if the data you want to validate is present
 1. If the feature you want to validate isn't enabled, enable it.
    * Probably the correct option: Change the weblog/application image
    * Enable it through run.sh
    * Enable it through an environment variable
 1. [Add a test to verify your data, sending any requests as needed](#how-do-i-add-a-new-test).
 1. Disable the test for languages which don't yet implement it
 1. Submit a pull request, ask for review

However, there are many scenarios where a test may not be so simple to implement.

This document aims to give a working understanding of the parts of system-tests, and how to troubleshoot them.

## What are the components of a running test?

When an end-to-end scenario is running, these are the main pieces:

 - [Host pytest](#host-pytest) (aka "runner")
   - Runs on the host (not in a container). Sends HTTP to the weblog and asserts on captured interfaces
 - [Customer application](#weblog) (aka "weblog")
   - Swappable webapp language module that replicate a real customer application. Mostly a simple HTTP application in the form of a docker container.
 - [Proxy](#proxy)
   - Single [mitmdump](https://mitmproxy.org/) container that intercepts library and agent traffic
 - [Agent](#agent)
   - Datadog agent container

```mermaid
flowchart TD
    HOST[Host pytest] -->|HTTP requests| WEBLOG
    WEBLOG[Customer application] -->|library traffic| PROXY
    PROXY[Proxy] -->|forward| AGENT
    AGENT[Agent] -->|agent traffic| PROXY
    PROXY -.->|JSON dumps| HOST
```

pytest on the host sends requests directly to the [weblog](weblogs/README.md) (the customer application).
The weblog tracer talks to the [proxy](#proxy) (`DD_AGENT_HOST=proxy`), which forwards that traffic to the agent.
The agent talks back through the **same** proxy (`DD_PROXY_HTTPS`).
The proxy writes the intercepted messages as JSON under `logs_<scenario>/interfaces/` ([library](../edit/library-interface-validation-methods.md) and [agent](../edit/agent-interface-validation-methods.md)).
Tests read those files; they do not receive a live dump stream.

By default the proxy mocks backend intake instead of forwarding it to Datadog.
Some scenarios disable that mock, and some tests query Datadog APIs from the host via [`interfaces.backend`](../edit/backend-interface-validation-methods.md). Though, it's highly discouraged to use any real backend, as our backend constraints does not guarantee time limit compatible with a test session : using the real backend will make tests sessions very unreliable.

## What are system-tests bad for?

 - Combinatorial-style tests (Permutations of framework runtimes, 3rd libraries versions, operating systems)
 - Cloud deployments, kubernetes, distributed deployments
 - Immediately knowing the reason a feature fails
 - Problems or features which are not shared across tracers
 - Performance or throughput testing

 *Examples of bad candidates:*
  - The .NET tracer must not write invalid [IL](https://en.wikipedia.org/wiki/Common_Intermediate_Language) for it's earliest supported runtime
  - The startup overhead of the Java tracer is less than 3s for a given sample application
  - The python tracer must not fail to retrieve traces for a version range of the mongodb library

## What are system-tests good for?

 - Catching regressions on shared features
 - Wide coverage in a short time frame
 - Shared test coverage across all tracer libraries
 - Ensuring requirements for shared features are met across tracer libraries
 - testing a set of version of any datadog component

*Examples of good candidates:*
  - `DD_TAGS` must be parsed correctly and carried as tags on all traces
  - Tracer libraries must be able to communicate with the agent through Unix Domain Sockets
  - Sampling rates from the agent are respected when not explicitly configured
  - All tracer libraries log consistent diagnostic information at startup

## How do I add a new test?

The default folder to add new tests is `./tests`.

The framework used for running tests is [pytest](https://docs.pytest.org/).

For a test to be run, it must have the filename prefix `test_`.

Follow the [example and instructions provided within `./docs/understand/test_template.py`](/docs/understand/test_template.py).

## How do I troubleshoot a failing test?

As system tests is blackbox testing, there will likely be very little information about your failing test in output.

The first method of troubleshooting should be to inspect the logs folder.

The folder is `./logs/` for the default scenario, or `./logs_<scenario_name>` for other scenatrios

```mermaid
flowchart TD
    RUNTEST[./run.sh] -->|pass| PASS
    PASS[Success]
    RUNTEST -->|fail| TESTFAIL
    TESTFAIL[Test Failures] --> FAILURELOG
    FAILURELOG[Logs Directory] --> LOGDECISION
    LOGDECISION(Enough information?) -->|no| ADDLOGS
    ADDLOGS[Add more logs] --> RUNTEST
    LOGDECISION -->|yes| FIXTEST
    FIXTEST[Fix tests] --> RUNTEST
```

## How do I troubleshoot a container?

The `./run.sh` script starts the containers in the background.

Often, knowing how a container fails to start is as simple as adding `--sleep` to your `run` command and observing the output.

If there are more in depth problems within a container you may need to adjust the Dockerfile.
 - re-run `./build.sh`
 - start the container via `./run.sh <SCENARIO-NAME> --sleep`
 - `docker exec -it {container-id} bash` to diagnose from within the container

## What is the structure of the code base?

The entry points of system-tests are observable from `./.github/workflows/ci.yml`.

The `./build.sh` script calls into a nested `./utils/build/build.sh` script.
 - [Click for details about the `./build.sh` script and options available](#building-the-system-tests).

The first argument to the `./build.sh` script is the language which is built: `./utils/build/docker/{language}`.
 - e.g., `./build.sh dotnet`

The `./run.sh` script runs the tests and relies 1-to-1 on what is built in the `./build.sh` step.
 - [Click for details about the `./run.sh` script and options available](#running-the-system-tests).

The run script ultimately calls the `./docker-compose.yml` file and whichever image is built with the `weblog` tag is tested.
 - [Click for detail about how the images interact with eachother](#what-are-the-components-of-a-running-test)

## Building the System Tests

The first argument to the `./build.sh` script is the language (`$TEST_LIBRARY`) which is built: `./utils/build/docker/{language}`.
 - `./build.sh cpp`
 - `./build.sh ruby`
 - `./build.sh python`
 - `./build.sh php`
 - `./build.sh nodejs`
 - `./build.sh java`
 - `./build.sh golang`
 - `./build.sh dotnet`

There are explicit arguments available for more specific configuration of the build.
 - i.e., `./build.sh {language} --weblog-variant {dockerfile-prefix}`
 - e.g., `./build.sh python --weblog-variant flask-poc`
 - shorter version: ./build.sh python -w flask-poc


These arguments determine which Dockerfile is ultimately used in the format of: `./utils/build/docker/{language}/{dockerfile-prefix}.Dockerfile`

## Running the System Tests

The build script must be successful before running the tests.

The first argument to the `./run.sh` script is the scenario (`$SCENARIO`) which defaults to `DEFAULT`.
 - `./run.sh`
 - `./run.sh DEFAULT`
 - `./run.sh SAMPLING`
 - `./run.sh PROFILING`

You can see all available scenarios within the `./run.sh` script.

The run script sets necessary variables for each scenario, which are then used within the `docker-compose.yml` file.

When debugging tests, it may be useful to only run individual tests, following this example:
 - `./run.sh tests/appsec/test_conf.py::Test_StaticRuleSet::test_basic_hardcoded_ruleset`
 - `./run.sh tests/test_traces.py::Test_Misc::test_main`

## Host pytest

Tests run on the host via [`./run.sh`](../execute/run.md) (pytest).
There is no tests container in the scenario topology.

The runner sends traffic to the weblog (published host ports) and validates messages the [proxy](#proxy) wrote under `logs_<scenario>/interfaces/` ([log folder structure](../execute/logs.md)).

## Weblog

The weblog (customer application) is the pluggable component for each language.
It is a web application that exposes consistent endpoints across all implementations.

If you are introducing a new Dockerfile, or looking to modify an existing one, remember that they are built using this convention in arguments: `./utils/build/docker/{language}/{dockerfile-prefix}.Dockerfile`.

The shared application docker file is a good place to add any configuration needed across languages and variants.

## Proxy

There is **one** proxy container (`proxy`).
It is [mitmdump](https://mitmproxy.org/).

The proxy listens on several ports and uses the listen port to know where a request came from:

- Weblog / library traffic is reverse-proxied to the agent
- Agent intake is intercepted because the agent is configured with `DD_PROXY_HTTPS` / `DD_PROXY_HTTP`

Captured request/response pairs are written as JSON to `logs_<scenario>/interfaces/<interface>/` on a volume shared with the host.

## Agent

The agent container uses `datadog/agent:latest`.

## Testing a local version of the tracer

Read the instructions in [the binaries documentation](/docs/execute/binaries.md).

In short, copy your tracer version to the `./binaries` folder, and build and run as usual.
