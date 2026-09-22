# AWS SSI PHP Profiling Flakiness Investigation

**Date:** 2026-09-22
**Scenarios:** `CONTAINER_AUTO_INJECTION_INSTALL_SCRIPT_PROFILING`,
`SIMPLE_AUTO_INJECTION_PROFILING`
**Component under test:** `datadog-apm-library-php`
`1.26.0-dev.d354bebf127c371b163fb94b4954db5ad0b35245`
**Status:** The product-level root cause is not proven by the available artifacts.
The strongest code-level mechanism is a destructive, one-shot PHP profile upload.
The latest reproduction did not activate the intended diagnostics because they were
configured for a different scenario.

## Executive summary

The failure is not caused by the AWS SSI scenario omitting
`DD_PROFILING_ENABLED`. The stable configuration file contains:

```yaml
apm_configuration_default:
  DD_PROFILING_ENABLED: auto
```

PHP accepts `auto` as `true`. The loader's fallback
`datadog.profiling.enabled=0` does not race with this value: stable configuration
has deterministic precedence over the fallback INI value.

The test finds the trace and its `runtime-id`, but the Profiles API repeatedly
returns HTTP 200 with an empty result for that runtime ID. A passing comparison
also returns empty results initially, then finds the profile approximately
103 seconds after the application request.

Three scenario variables create a misleading expectation that PHP will upload
after five seconds:

- `DD_PROFILING_UPLOAD_PERIOD=5`
- `DD_INTERNAL_PROFILING_LONG_LIVED_THRESHOLD=1500`
- `DD_PROFILING_START_FORCE_FIRST=true`

The PHP profiler does not implement these settings. Its upload period is
hardcoded to 67 seconds.

The strongest defect found in `dd-trace-php` is:

1. Every 67 seconds the collector removes all current profiles with
   `profiles.drain()`.
2. Each profile is queued and sent once.
3. A full channel, serialization error, UDS/HTTP error, or HTTP status at or
   above 400 only produces a warning.
4. There is no retry and no requeue, so the profile window is permanently lost.

This mechanism explains a trace succeeding while profiling fails, and it explains
PASS → FAIL → PASS behavior without a code change. It remains a high-confidence
hypothesis rather than a proven cause for a particular failed run because none of
the failed artifacts contains the profiler upload result.

## Artifacts examined

Original comparison:

- Failed:
  `/Users/roberto.montero/Documents/temp/20260921/reports/logs_container_auto_injection_install_script_profiling`
- Passed:
  `/Users/roberto.montero/Documents/temp/20260921/reports 2/logs_container_auto_injection_install_script_profiling`

Latest failed reproduction:

- `/Users/roberto.montero/Documents/temp/20260921/reports 3/logs_simple_auto_injection_profiling`

Exact source snapshots:

- `dd-trace-php`: `d354bebf127c371b163fb94b4954db5ad0b35245`
- `libdatadog`: `817cf820`
- `auto_inject`: `3ec11219`

## Original failed versus passed run

Both runs used the same PHP library and injector revisions:

- `datadog-apm-library-php`:
  `1.26.0-dev.d354bebf127c371b163fb94b4954db5ad0b35245`
- `datadog-apm-inject`:
  `0.71.1-dev.b0d6e40.glci2061052267.g3ec11219`

They did not use the same environment:

- Failed: Oracle Linux 9.3 amd64,
  `test-app-php-container-83`, Debian/glibc PHP image.
- Passed: AlmaLinux 8 amd64, `test-app-php-alpine`, musl PHP image.

Therefore, that pair alone does not prove flakiness on one exact target. The CI
history described below supplies the stronger PASS → FAIL → PASS evidence.

In both artifacts:

- SSI injection completed.
- Tracing worked.
- The stable configuration contained `DD_PROFILING_ENABLED: auto`.
- The scenario propagated the three profiling variables listed above.
- The test extracted `runtime-id` from the root trace span and queried profiles
  using `runtime-id:<value>`.

In the failed run, the Profiles API returned HTTP 200 with `{"data":[]}` on every
attempt. There was no 429 response. In the passed run, the same API initially
returned empty data and found a profile at 04:10:32, approximately 95 seconds
after profile polling began and 103 seconds after the application request.

This proves that some ingestion/indexing delay is normal, but it does not prove
that the failed profile reached the Agent or backend.

## PHP activation and configuration

### `DD_PROFILING_ENABLED=auto` enables PHP profiling

The PHP parser explicitly accepts `auto` as a true value:

```rust
if value.eq_ignore_ascii_case("1")
    || value.eq_ignore_ascii_case("on")
    || value.eq_ignore_ascii_case("yes")
    || value.eq_ignore_ascii_case("true")
    || value.eq_ignore_ascii_case("auto")
```

Source:
[`profiling/src/config.rs`](https://github.com/DataDog/dd-trace-php/blob/d354bebf127c371b163fb94b4954db5ad0b35245/profiling/src/config.rs#L883-L909).

### The loader fallback is not a race

SSI's PHP loader inserts `datadog.profiling.enabled=0` only when no INI value is
already present:

```c
if (!ddloader_ini_get_configuration(
        ZEND_STRL("datadog.profiling.enabled"))) {
    ddloader_ini_set_configuration(
        config,
        ZEND_STRL("datadog.profiling.enabled"),
        ZEND_STRL("0"));
}
```

Source:
[`loader/dd_library_loader.c`](https://github.com/DataDog/dd-trace-php/blob/d354bebf127c371b163fb94b4954db5ad0b35245/loader/dd_library_loader.c#L287-L294).

The profiler then resolves configuration during initialization. The effective
precedence is fleet stable configuration, environment, cached environment, local
stable configuration, INI, then default. Therefore, the local stable value
deterministically overrides the loader's INI fallback. The YAML is created before
the application container in the examined system-tests runs and is mounted
read-only into the container. No evidence supports an inode or mount timing race
in these artifacts.

### PHP ignores the scenario's upload acceleration settings

The exact PHP source contains no configuration entries for:

- `DD_PROFILING_UPLOAD_PERIOD`
- `DD_INTERNAL_PROFILING_LONG_LIVED_THRESHOLD`
- `DD_PROFILING_START_FORCE_FIRST`

Instead, the periods are compile-time constants:

```rust
const UPLOAD_PERIOD: Duration = Duration::from_secs(67);
const WALL_TIME_PERIOD: Duration = Duration::from_millis(10);
```

Sources:
[`UPLOAD_PERIOD`](https://github.com/DataDog/dd-trace-php/blob/d354bebf127c371b163fb94b4954db5ad0b35245/profiling/src/profiler/mod.rs#L65) and
[`WALL_TIME_PERIOD`](https://github.com/DataDog/dd-trace-php/blob/d354bebf127c371b163fb94b4954db5ad0b35245/profiling/src/profiler/mod.rs#L144).

Consequently, the six-second wait in
[`tests/auto_inject/utils.py`](../../tests/auto_inject/utils.py) does not wait for
a PHP profile upload. Profile polling continues afterward, so this mismatch does
not by itself guarantee a failure, but it makes the test comment and timing
assumption incorrect for PHP.

## Destructive one-shot upload

At each timeout, `dd-trace-php` drains the profile map before enqueueing uploads:

```rust
for (index, profile) in profiles.drain() {
    let message = UploadMessage::Upload(/* ... */);
    if let Err(err) = self.upload_sender.try_send(message) {
        warn!("Failed to upload profile: {err}");
    }
}
```

Source:
[`profiling/src/profiler/mod.rs`](https://github.com/DataDog/dd-trace-php/blob/d354bebf127c371b163fb94b4954db5ad0b35245/profiling/src/profiler/mod.rs#L391-L422).

The uploader performs one send:

```rust
match self.upload(request, &mut last_cpu) {
    Ok(status) => {
        if status >= 400 {
            warn!("Unexpected HTTP status when sending profile (HTTP {status}).")
        } else {
            info!("Successfully uploaded profile (HTTP {status}).")
        }
    }
    Err(err) => warn!("Failed to upload profile: {err}"),
}
```

Source:
[`profiling/src/profiler/uploader.rs`](https://github.com/DataDog/dd-trace-php/blob/d354bebf127c371b163fb94b4954db5ad0b35245/profiling/src/profiler/uploader.rs#L159-L180).

There is no retry or requeue in either path. Tracing uses a separate transport
pipeline, so successful tracing does not imply successful profiling.

## Runtime-ID correlation

The system-test obtains `runtime-id` from the root span and queries:

```text
-_dd.hotdog:* runtime-id:<root-span-runtime-id>
```

This is the correct correlation strategy. The runtime IDs printed by the
injector/preload telemetry belong to injector processes or telemetry forwarding
contexts. They must not be compared directly with the tracer/profile runtime ID.

The failed artifacts do not expose the runtime ID embedded in an uploaded
profile. Therefore, a profile uploaded under a different runtime ID remains an
open alternative to a missing upload.

## CI history

The historical CI data does not expose a deterministic first bad
`system-tests` commit.

### Earliest isolated exact-scenario failure found

For the encoded `CO1B` target
(`CONTAINER_AUTO_INJECTION_INSTALL_SCRIPT_PROFILING`) on 2025-07-07:

- PASS, job `1015202446`, 02:11 UTC.
- FAIL, job `1015221353`, 04:00 UTC.
- PASS, job `1015245483`, 05:58 UTC.

All three used system-tests SHA
`2c4903c56cae3f3d1ba67b8d29fb9100d4fa3a3e`. The failed job and subsequent
passing job were in pipeline `69734116`.

Clusters on 2025-07-01 and 2025-07-04 affected other languages too, so they are
not evidence of a PHP-specific introduction point.

### Recent recurrence

The first recent isolated PHP failure found was the encoded `SID0` target
(`SIMPLE_AUTO_INJECTION_PROFILING`) on 2026-07-10 at 15:31 UTC, job
`1849750698`, using PHP Alpine. It was surrounded by passing executions, including
a pass shortly after the failure.

A 30-day CI query returned 33 PHP jobs failing with the Profiles API timeout and
no equivalent non-PHP jobs in the same query. This indicates a PHP-specific
failure mode, while the adjacent passes confirm that it is nondeterministic.

## Commit investigation

### Strongest mechanism, but not a recent regression

- [`1ee59169`](https://github.com/DataDog/dd-trace-php/commit/1ee591694399c7831be5290832d7be62d70a5528)
- [`fe9c3579`](https://github.com/DataDog/dd-trace-php/commit/fe9c357943c0c744e9a7213ea7328b7443b7b533)

These commits introduced/refactored the periodic collector and uploader behavior.
The one-shot, destructive semantics remain in `d354bebf`. They explain the
failure mode but are too old to be a recent regression.

### Historical crash candidate

[`dd-trace-php #3319`](https://github.com/DataDog/dd-trace-php/pull/3319),
commit `c748dcca`, was merged on 2025-07-11. It fixed an invalid
`execute_data.opline` dereference in the sampler. This is temporally compatible
with the 2025-07-07 observation, but it should leave a crash/restart signal and
has already been fixed. The current artifacts contain no core dump or process
restart.

### Weak recent candidate

[`dd-trace-php #4038`](https://github.com/DataDog/dd-trace-php/pull/4038),
commit `268dcfbf`, was merged on 2026-07-10 at 14:12 UTC, 79 minutes before the
first recent isolated failure found. It updates dependencies and profiler
internals, but does not change upload cadence, `profiles.drain()`, retries,
runtime-ID creation, or MINIT/RINIT startup. A pass occurred shortly after the
failure. Temporal proximity alone is insufficient to identify it as the cause.

### Runtime-ID changes are too recent

- [`dd-trace-php #4077`](https://github.com/DataDog/dd-trace-php/pull/4077),
  commit `018f2129`, merged 2026-08-14.
- [`dd-trace-php #4213`](https://github.com/DataDog/dd-trace-php/pull/4213),
  commit `d354bebf`, merged 2026-09-21.

Failures predate both changes. They cannot explain the historical origin,
although a current runtime-ID mismatch still requires direct profile evidence to
exclude.

### `auto_inject`

- [`auto_inject #649`](https://github.com/DataDog/auto_inject/pull/649) mounts
  `application_monitoring.yaml`. A mount timing race is theoretically possible
  if the file is replaced after container creation, but system-tests creates it
  first and the examined logs show the expected mount.
- `#651` removed DJM/Java configuration and has no direct PHP profile transport
  mechanism.
- [`auto_inject #696`](https://github.com/DataDog/auto_inject/pull/696) mainly
  affects Ruby environment prepending and was released after the earliest
  failure.
- Neither `v0.68` nor current commit `3ec11219` exposes a convincing change that
  would drop only PHP profiles while preserving traces.

### `libdatadog`

The investigated PHP releases pinned these `libdatadog` revisions:

- PHP 1.10: `09474fc1`
- PHP 1.11: `8580cf5d`
- PHP 1.21: `93e97238`
- PHP 1.22: `cd90e50a`
- PHP 1.23: `6a6d4a53`
- Current reproduction: `817cf820`

The profiling exporter used by PHP is materially unchanged between the PHP 1.21
and 1.22 pins. No dated exporter regression matching the PASS → FAIL → PASS
history was found.

## Latest reproduction analysis

### Environment

The latest artifact is not the original container install-script scenario. It is:

- Scenario: `SIMPLE_AUTO_INJECTION_PROFILING`
- Test:
  `TestSimpleInstallerAutoInjectManualProfiling::test_profiling[test-app-php-alpine]`
- VM: Fedora 36 arm64
- PHP: 8.3.33 Alpine/musl
- Agent: `7.78.4-1`
- Injector: `0.71.1-dev...3ec11219`
- PHP library: `1.26.0-dev...d354bebf`

### Timeline

1. **09:05:35** — The provision prints the application variables. It contains
   the three unsupported acceleration settings, but not the new diagnostics.
2. **09:05:36** — The runc wrapper mounts
   `/etc/datadog-agent/application_monitoring.yaml` and
   `/var/run/datadog`. The stable file contains
   `DD_PROFILING_ENABLED: auto`.
3. **09:05:36** — A helper `php -v` invocation visibly loads
   `datadog-profiling.so`. These lines do not prove that the long-lived server
   process initialized the profiler.
4. **09:05:36** — The actual server starts as
   `php -S 0.0.0.0:18080`.
5. **09:05:37** — The provisioning health request succeeds.
6. **09:05:54** — The test request succeeds with trace ID
   `39025901734954581`.
7. **09:06:04** — The trace is found. Its runtime ID is
   `05356364-5ffe-45c7-abba-f053034b19d7`.
8. **09:06:04–09:09:33** — Every Profiles API response is HTTP 200 with
   `{"data":[]}`. There is no rate limiting.
9. **09:09:40** — Final collection shows the application container still up
   after approximately four minutes. No core dump, OOM, segfault, or restart is
   present.

### The intended diagnostics were not active

The artifact directly contradicts the assumption that all new flags were
enabled. The provisioned environment does not contain:

- `DD_PROFILING_LOG_LEVEL=debug`
- `DD_TRACE_DEBUG=1`
- `SYSTEM_TESTS_PROFILING_DEBUG=1`

The instrumentation commit used by this run,
[`eb2fd404`](https://github.com/DataDog/system-tests/commit/eb2fd404ad896c422e19459b10820b16001e49d0),
added these values only to
`CONTAINER_AUTO_INJECTION_INSTALL_SCRIPT_PROFILING`, while the run executed
`SIMPLE_AUTO_INJECTION_PROFILING`.

The consequences are visible:

- `php-process-diagnostics.log` was not generated because its collector exits
  when `SYSTEM_TESTS_PROFILING_DEBUG=1` is absent.
- The application did not emit the `SYSTEM_TESTS_PROFILING_DEBUG` record showing
  the real server's loaded extension and effective INI value.
- No `ddprof_time` or `ddprof_upload` thread snapshot exists.
- No PHP profiler message reports `Successfully uploaded profile`,
  `Failed to upload profile`, `Unexpected HTTP status`, or
  `No profiles to upload`.
- `dd-agent-diagnostics.log` is empty because this scenario uses the host Agent,
  while the original final snapshot handled only a `dd-agent` container.
- Downloading `/var/log/datadog` failed with `PermissionError`, so the host
  Agent's `trace-agent.log` is also unavailable.

### What this reproduction proves

- The trace path works.
- The stable profiling configuration exists and is mounted.
- The process remains alive.
- The requested runtime ID has no queryable profile during the observed period.
- The backend query itself is healthy: all responses are HTTP 200.

### What it cannot distinguish

The missing evidence leaves these mutually exclusive causes open:

1. The real PHP server did not initialize the profiler.
2. The profiler initialized but produced no uploadable window.
3. The upload failed before reaching the Agent and was discarded without retry.
4. The Agent rejected or failed to forward the profile.
5. The profile was uploaded with a runtime ID different from the trace.
6. The backend accepted the profile but did not make it queryable in time.

Accordingly, it would be incorrect to claim a certain product-level root cause
from this reproduction.

## Root-cause assessment

### Certain finding

The latest run did not collect the diagnostics required for a definitive result
because the debug environment was attached to the wrong scenario and the Agent
collector handled only a containerized Agent.

### Highest-confidence product hypothesis

A transient failure on the first useful PHP upload window is made permanent by
`profiles.drain()` plus a one-shot uploader with no retry or requeue. This is the
only discovered product mechanism that naturally explains:

- successful tracing;
- missing profiling;
- PHP-specific failures;
- PASS → FAIL → PASS with unchanged code; and
- recovery on a complete rerun.

It is not yet a proven event in the failed run because the uploader log is
absent.

## Follow-up instrumentation

The current system-tests working tree now:

- enables `DD_PROFILING_LOG_LEVEL=debug`, `DD_TRACE_DEBUG=1`, and
  `SYSTEM_TESTS_PROFILING_DEBUG=1` for
  `SIMPLE_AUTO_INJECTION_PROFILING`; and
- appends diagnostics from a host Agent service, including `agent.log` and
  `trace-agent.log`, when there is no `dd-agent` container.

The next failed run can close the diagnosis:

- `Failed to upload profile` or HTTP >= 400, followed by no retry, proves the
  destructive uploader path.
- `Successfully uploaded profile (HTTP 2xx)` with the expected runtime ID but no
  Agent receipt moves the fault to the local Agent boundary.
- Agent receipt/forward success with no backend profile moves the fault beyond
  the Agent.
- A successful upload carrying a different runtime ID proves correlation
  mismatch.
- Missing `ddprof_time`/`ddprof_upload` threads or an effective
  `datadog.profiling.enabled=Off` proves initialization/configuration failure.

## Recommended fixes

### `dd-trace-php`

1. Do not permanently remove a profile window until a 2xx response is received.
2. Add bounded retries with backoff for serialization, channel, UDS/HTTP, and
   retryable HTTP failures.
3. Requeue or retain failed windows within a bounded memory budget.
4. Log the runtime ID, profile time range, endpoint, and attempt number at debug
   level.
5. Add a test that injects one transient upload failure and verifies eventual
   delivery.

### `system-tests`

1. Do not describe the six-second sleep as waiting for a PHP upload.
2. Remove or clearly document PHP-unsupported acceleration variables.
3. Keep generating a controlled request workload across at least one real
   67-second PHP upload period.
4. Preserve process-thread, profiler, and Agent diagnostics on every profiling
   failure.
5. On failure, perform a secondary profile query broad enough to distinguish
   “not uploaded” from “uploaded under another runtime ID”.

## Related system-tests files

- [AWS SSI debugging documentation](../understand/scenarios/onboarding.md)
- [Profiling scenario definitions](../../utils/_context/_scenarios/__init__.py)
- [AWS SSI log collection](../../utils/onboarding/debug_vm.py)
- [Auto-inject test timing](../../tests/auto_inject/utils.py)
- [Backend trace/profile correlation](../../utils/onboarding/backend_interface.py)
