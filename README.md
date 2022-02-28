## System tests

Workbench designed to run advanced tests (integration, smoke, functionnal, fuzzing and performance)

## Requirement

`bash`, `docker-compose`

## How to use ? 

Add a valid staging `DD_API_KEY` environment variable (you can set it in a `.env` file). Then:

```mermaid
flowchart TD
    BUILDNODE[./build.sh node] --> BUILT
    BUILDDOTNET[./build.sh dotnet] --> BUILT
    BUILDJAVA[./build.sh java] --> BUILT
    BUILDGO[./build.sh golang] --> BUILT
    BUILDPHP[./build.sh php] --> BUILT
    BUILDPY[./build.sh python] --> BUILT
    BUILT[Build complete] --> SCENARIO
    SCENARIO(Pick scenario) --> RUNDEFAULT
    SCENARIO --> RUNSAMPLING
    SCENARIO --> RUNMISC
    RUNDEFAULT[./run.sh] -->|wait| FINISH
    RUNSAMPLING[./run.sh SAMPLING] -->|wait| FINISH
    RUNMISC[./run.sh ....] -->|wait| FINISH
    FINISH[Tests complete] --> LOGS
    FINISH[Tests complete] --> OUTPUT
    OUTPUT[Test output in bash]
    LOGS[Logs directory per scenario]
```

More details in [build documentation](https://github.com/DataDog/system-tests/blob/master/docs/execute/build.md) and [run documentation](https://github.com/DataDog/system-tests/blob/master/docs/execute/run.md).

![Output on success](./utils/assets/output.png?raw=true)

**[Complete documentation](https://github.com/DataDog/system-tests/blob/master/docs)**

