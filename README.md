## What is system-tests?

A workbench designed to run advanced tests (integration, smoke, functional, fuzzing and performance) against our suite of dd-trace libraries.

When making changes to dd-trace, you'll commonly need to run the unmerged changes against the system tests (to ensure the feature is up to spec). But because system tests are outside of dd-trace-xx repos, testing against unmerged changes is not so straightforward. Various approaches  to this "chicken or the egg" problem are detailed [here](https://github.com/DataDog/system-tests/blob/main/docs/execute/how-to-approach-changes.md).

## Requirements

`bash`, `docker` and `python3.12`. More infos in the [documentation](https://github.com/DataDog/system-tests/blob/main/docs/execute/requirements.md)

## Weblog vs Parametric

System-tests contains two types of tests: "weblog" and "parametric." Weblog tests came first, parametric tests were developed later. Most of the docs in this repo refer to weblog tests, and many of the instructions apply to both weblog and parametric, but not all. You can find dedicated parametric instructions in the [parametric.md](https://github.com/DataDog/system-tests/blob/main/docs/scenarios/parametric.md).

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

