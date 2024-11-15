## What is system-tests?

A workbench designed to run advanced tests (integration, smoke, functional, fuzzing and performance) against our suite of dd-trace libraries.

## Requirements

`bash`, `docker` and `python3.12`.

We recommend to install python3.12 via pyenv: pyenv/pyenv#getting-pyenv. Pyenv is a tool for managing multiple python versions and keeping system tests dependencies isolated to their virtual environment. If you don't wish to install pyenv, instructions for downloading python 3.12 on your machine can be found below:

#### Ubuntu

```
sudo add-apt-repository ppa:deadsnakes/ppa
sudo apt update
sudo apt install python3.12 python3.12-distutils python3.12-venv python3.12-dev
curl https://bootstrap.pypa.io/get-pip.py -o get-pip.py
python3.12 get-pip.py
./build.sh -i runner
```

#### Windows

TODO

#### Mac

For Homebrew users :

```
brew install python@3.12
pip3.12 install virtualenv
```

## End-To-End vs Parametric

System-tests contains various testing scenarios; the two most commonly used are called "End-To-End" and "Parametric." Most of the docs in this repo refer to End-To-End tests, which were developed earlier and support a wider range of scenarios. Some of the instructions apply to both end-to-end and parametric (e.g. the [edit docs](./docs/edit/)), but not all. You can find dedicated parametric instructions in the [parametric.md](https://github.com/DataDog/system-tests/blob/main/docs/scenarios/parametric.md).

**End-To-End**

End-To-End tests are good for testing real-world scenarios — they incorporate "weblog" servers designed to mimick customer applications with automatic instrumentation, a "test-agent" to mimick the Datadog Agent, and communication with the Datadog backend. They support the full lifecycle of a trace (hence the name, "End-To-End"). Use End-To-End scenarios to test tracing integrations, security products, profiling, dynamic instrumentation, and more. When in doubt, use end-to-end.

**Parametric**

Parametric tests are designed to validate tracer and span interfaces. They are more lightweight and support testing features with many input parameters. They should be used to test operations such as creating spans, setting tags, setting links, injecting/extracting http headers, getting tracer configurations, etc.

## How to use

```mermaid
flowchart TD
    BUILDNODE[./build.sh nodejs] --> BUILT
    BUILDDOTNET[./build.sh dotnet] --> BUILT
    BUILDJAVA[./build.sh java] --> BUILT
    BUILDGO[./build.sh golang] --> BUILT
    BUILDPHP[./build.sh php] --> BUILT
    BUILDPY[./build.sh python] --> BUILT
    BUILDRUBY[./build.sh ruby] --> BUILT
    BUILT[Build complete] --> RUNDEFAULT
    RUNDEFAULT[./run.sh] -->|wait| FINISH
    FINISH[Tests complete] --> LOGS
    FINISH[Tests complete] --> OUTPUT
    OUTPUT[Test output in bash]
    LOGS[Logs directory per scenario]
```

Understand the parts of the tests at the [architectural overview](https://github.com/DataDog/system-tests/blob/main/docs/architecture/overview.md).

More details in [build documentation](https://github.com/DataDog/system-tests/blob/main/docs/execute/build.md) and [run documentation](https://github.com/DataDog/system-tests/blob/main/docs/execute/run.md).

![Output on success](./utils/assets/output.png?raw=true)

**[Complete documentation](https://github.com/DataDog/system-tests/blob/main/docs)**

