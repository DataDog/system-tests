---
name: system-tests-local
description: >
  Run Datadog system-tests parametric (or end-to-end) tests using locally built tracer libraries.
  Covers all 9 languages: Java, Python, Node.js, Go, Ruby, C++, .NET, PHP, Rust.
  Use when the user wants to "run system tests locally", "test my tracer changes",
  "run parametric tests", "test local build", "run system-tests with local dd-trace-*",
  or any variation of testing local tracer library changes against the system-tests suite.
allowed-tools: Agent Bash Read Grep Glob Write Edit TaskOutput
metadata:
  version: "2.0.0"
  tags: datadog,system-tests,parametric,local-build,tracing,dd-trace
---

# System Tests -- Local Build Runner

Run Datadog system-tests against locally built tracer libraries.

## Overview

The system-tests repo uses a `binaries/` folder to inject local tracer code into test containers.
The `prepare-local-build.sh` script automates all per-language preparation steps.

```bash
# Location (run from system-tests repo root)
./utils/scripts/prepare-local-build.sh
```

## Pre-flight

1. **Docker must be running.** If not:
   ```bash
   open -a Docker && while ! docker info &>/dev/null; do sleep 1; done
   ```

2. **Python venv with test dependencies:**
   ```bash
   cd ~/go/src/github.com/DataDog/system-tests
   # If .venv doesn't exist or is stale:
   python3 -m venv .venv
   .venv/bin/pip install --upgrade pip setuptools wheel
   .venv/bin/pip install -r requirements.txt
   ```

3. **Clean stale Docker state if needed:** `docker network prune -f`

## Core Workflow

### 1. Prepare binaries

```bash
./utils/scripts/prepare-local-build.sh <language> [path-to-tracer-repo] [--method <method>]
```

- **Languages:** java, nodejs, golang, python, ruby, rust, cpp, dotnet, php
- **Path is optional** -- defaults to `~/dd/dd-trace-<lang>` (e.g., `~/dd/dd-trace-java`)
- Use `--method` to override the default preparation method
- Use `--rebuild` to force a fresh build even if artifacts exist

### 2. Run tests

```bash
TEST_LIBRARY=<lang> ./run.sh PARAMETRIC -k "<test_name>"
```

### 3. Clean up

```bash
./utils/scripts/prepare-local-build.sh --clean <lang>
# Or clean all languages:
./utils/scripts/prepare-local-build.sh --clean
```

## Useful Script Commands

```bash
# See what's currently in binaries/
./utils/scripts/prepare-local-build.sh --status

# List all supported languages and methods
./utils/scripts/prepare-local-build.sh --list

# Force rebuild (removes cached artifacts before building)
./utils/scripts/prepare-local-build.sh java --rebuild
```

## Languages and Methods

| Language | Default Method | Other Methods | What It Does |
|----------|---------------|---------------|--------------|
| java | jars | -- | Builds JARs via Gradle if missing, copies to binaries/ |
| nodejs | local | clone | Creates pointer file for volume mount (fastest, no rebuild for code changes) |
| golang | clone | -- | Shallow clone into binaries/dd-trace-go |
| python | wheel | pip, s3 | Builds .whl via ddtest if missing; pip installs from PyPI; s3 loads by commit hash |
| ruby | clone | -- | Shallow clone into binaries/dd-trace-rb |
| rust | clone | -- | Shallow clone into binaries/dd-trace-rs |
| cpp | clone | -- | Shallow clone into binaries/dd-trace-cpp |
| dotnet | tarball | -- | Builds tar.gz via Nuke/Docker if missing, copies to binaries/ |
| php | tarball | -- | Builds tar.gz via build-debug-artifact if missing, copies to binaries/ |

## Examples

```bash
# Java -- build and test (auto-builds JARs if not present)
./utils/scripts/prepare-local-build.sh java ~/dd/dd-trace-java
TEST_LIBRARY=java ./run.sh PARAMETRIC -k "test_distributed_headers"
./utils/scripts/prepare-local-build.sh --clean java

# Node.js -- volume mount (instant, no rebuild needed for code changes)
./utils/scripts/prepare-local-build.sh nodejs ~/dd/dd-trace-js
TEST_LIBRARY=nodejs ./run.sh PARAMETRIC -k "test_start_span"
./utils/scripts/prepare-local-build.sh --clean nodejs

# Python -- build wheel via ddtest
./utils/scripts/prepare-local-build.sh python ~/dd/dd-trace-py
TEST_LIBRARY=python ./run.sh PARAMETRIC -k "test_start_span"
./utils/scripts/prepare-local-build.sh --clean python

# Python -- install from PyPI (no local repo needed)
./utils/scripts/prepare-local-build.sh python --method pip
TEST_LIBRARY=python ./run.sh PARAMETRIC -k "test_start_span"
./utils/scripts/prepare-local-build.sh --clean python

# Python -- load from S3 by commit hash (no local repo needed)
./utils/scripts/prepare-local-build.sh python <commit-hash> --method s3
TEST_LIBRARY=python ./run.sh PARAMETRIC -k "test_start_span"
./utils/scripts/prepare-local-build.sh --clean python

# .NET -- build tarball via Docker (auto-builds if not present)
./utils/scripts/prepare-local-build.sh dotnet ~/dd/dd-trace-dotnet
TEST_LIBRARY=dotnet ./run.sh PARAMETRIC -k "test_start_span"
./utils/scripts/prepare-local-build.sh --clean dotnet
```

## Known ARM Mac Issues

The script handles building and copying for all languages, but some ARM-specific
Dockerfile issues in system-tests may require manual workarounds:

### C++ -- TARGETARCH Dockerfile fix

The parametric Dockerfile hardcodes an amd64-only base image. Apply this temporary fix:

```bash
sed -i '' 's/FROM datadog\/docker-library:dd-trace-cpp-ci-23768e9-amd64/ARG TARGETARCH=arm64\nFROM datadog\/docker-library:dd-trace-cpp-ci-23768e9-${TARGETARCH}/' \
  utils/build/docker/cpp/parametric/Dockerfile

# Run tests, then revert:
git checkout -- utils/build/docker/cpp/parametric/Dockerfile
```

### .NET -- LD_PRELOAD on ARM

The parametric Dockerfile sets `LD_PRELOAD` to an x64-only continuous profiler `.so`.
Comment it out for ARM:

```bash
sed -i '' 's|^ENV LD_PRELOAD=/opt/datadog/continuousprofiler/Datadog.Linux.ApiWrapper.x64.so|# ENV LD_PRELOAD=/opt/datadog/continuousprofiler/Datadog.Linux.ApiWrapper.x64.so|' \
  utils/build/docker/dotnet/parametric/Dockerfile

# Run tests, then revert:
git checkout -- utils/build/docker/dotnet/parametric/Dockerfile
```

### .NET -- ARM build notes

On ARM Mac, the .NET build (triggered automatically by the script) may hit:
- Missing `Datadog.Linux.ApiWrapper.x64.so` at ZipMonitoringHome step. Workaround: create dummy files:
  ```bash
  touch ~/dd/dd-trace-dotnet/tracer/src/bin/artifacts/linux-arm64/Datadog.Linux.ApiWrapper.x64.so
  touch ~/dd/dd-trace-dotnet/tracer/src/bin/artifacts/linux-musl-arm64/Datadog.Linux.ApiWrapper.x64.so
  ```

### PHP -- system-tests fixes

Two fixes may be needed in system-tests for PHP on ARM:
1. `utils/_context/component_version.py` -- strip PHP startup warnings from version string
2. `utils/build/docker/php/common/install_ddtrace.sh` -- conditionally enable profiling

## Useful Test Candidates

Good parametric tests for smoke-testing across all languages:

- `test_headers_datadog.py::Test_Headers_Datadog::test_distributed_headers_extract_datadog_D001` -- basic Datadog header propagation
- `test_parametric_endpoints.py::Test_Parametric_DDSpan_Start::test_start_span` -- basic span creation

## Running Multiple Languages

Run sequentially to avoid Docker resource contention. Clean `binaries/` between runs
or let them coexist (each language uses different filenames/directories).

If you hit Docker network errors: `docker network prune -f`

## Key Files

- **Script:** `utils/scripts/prepare-local-build.sh`
- **Binaries docs:** `docs/execute/binaries.md`
- **Parametric scenario:** `utils/_context/_scenarios/parametric.py`
- **Docker fixtures:** `utils/_context/_scenarios/_docker_fixtures.py`
- **Install scripts:** `utils/build/docker/<lang>/install_ddtrace.sh`
- **Parametric Dockerfiles:** `utils/build/docker/<lang>/parametric/Dockerfile`
