# K8s library-injection init-container OOM investigation

## Executive summary

The configured `256Mi` memory limit caused the reproduced Kubernetes
library-injection trace failures. Kubernetes killed `copy-lib.sh` with exit
code 137 (`OOMKilled` and `TaskOOM`). On restart, the init container removed
the partial tracer package and exited with code 0 without restoring it. The
application then started without a tracer, and the tests received no traces.

A controlled A/B comparison isolated the memory setting: the exact failures
at `256Mi` passed at `512Mi`.

This conclusion applies only to the reproduced trace failures. The report does
not prove that the profiling or Kubernetes API-server failures had the same
cause. It also does not explain why `256Mi` became insufficient.

Tracking bug: [INPLAT-1393](https://datadoghq.atlassian.net/browse/INPLAT-1393)

## Incident scope

The original nightly executions were:

- [Python scheduled pipeline 150816382](https://gitlab.ddbuild.io/DataDog/system-tests/-/pipelines/150816382)
- [PHP scheduled pipeline 150817529](https://gitlab.ddbuild.io/DataDog/system-tests/-/pipelines/150817529)

The pipelines reported 23 failures:

- eight `No traces found` failures: two in Python and six in PHP;
- twelve PHP positive-profiling failures;
- three Kubernetes API-server connectivity failures.

The OOM mechanism is confirmed for reproduced trace failures. It is a
plausible but unconfirmed explanation for the profiling failures. This report
contains no evidence linking the API-server failures to the OOM.

Non-K8s failures introduced by the temporary diagnostic unit test are excluded
from this analysis.

## Established facts

### Controlled memory comparison

- [Draft PR #8384](https://github.com/DataDog/system-tests/pull/8384)
  retained the `256Mi` limit, added early init-container diagnostics, and
  produced five distinct K8s trace failures.
- [Draft PR #8385](https://github.com/DataDog/system-tests/pull/8385) used the
  same diagnostics and matrix with a `512Mi` limit. All 248 K8s jobs passed,
  including the five exact matrix cells that failed in PR #8384.
- Both diagnostic PRs used Cluster Agent `7.85.0`. The configured
  init-container memory was the only reported difference.

### Captured PHP failure

PR #8384 captured the failure state for this PHP UDS job:

- Scenario: `K8S_LIB_INJECTION_UDS`
- Library: `php@1.27.0`
- Cluster Agent: `7.85.0`
- Injector: `latest_snapshot`
- Helm chart: `3.264.0`
- Lib-init image: `dd-lib-php-init:latest`
- Lib-init digest:
  `sha256:e796a4c56a4af00c3464854c9ab8c76daef81b14e7d83e531326f39ad72f5234`
- Reported compressed image size: 193 MB
- Init-container memory request and limit: `256Mi`

The first init-container attempt started at `08:51:02` and was killed at
`08:51:04`. Kubernetes recorded:

- exit code `137`;
- reason `OOMKilled`;
- `TaskOOM` for the same container ID;
- `restart_count: 1`.

The restarted container logged:

```text
Copying dd-trace-php has previously failed, removing dd-trace-php package
```

It then exited with code 0. The injector init container also completed.
Injector telemetry reported success over UDS but reported
`tracer_version: unknown`. No trace payload was received, and repeated
`/test/traces` requests returned an empty result.

### Captured Python failure

An earlier Python artifact recorded the same sequence, including a direct
`TaskOOM` event in `datadog-lib-python-init`.

### Matrix observations

Across the nightly pipelines and PR #8384:

- no Python failure had an exact parameter match;
- only one PHP trace failure had an exact parameter match;
- failures moved between UDS and non-UDS scenarios, Cluster Agent variants,
  injector `latest` and `latest_snapshot`, and lib-init `latest` and
  `latest_snapshot`.

The common condition was the admission-controller path with an explicit
`256Mi` init-container limit.

## Strong inferences

### Failure sequence

The evidence supports this sequence:

1. `copy-lib.sh` exceeds the `256Mi` limit.
2. Kubernetes kills the init container and leaves a partial tracer package.
3. On restart, the recovery path removes the partial package and exits with
   code 0 without restoring it.
4. The application starts without the tracer and emits no traces.

### Component implications

The movement between matrix cells means no specific tracer, injector tag,
Cluster Agent variant, lib-init tag, or UDS mode explains the failures by
itself.

- **Cluster Agent:** Version `7.85.0` cannot explain the difference between
  the diagnostic PRs because both used that version. The Cluster Agent remains
  part of the configuration path because it applies the requested resources.
- **Injector and UDS:** The injector completed and sent telemetry. The
  evidence places the failure in the library-copy step, not in injector
  execution or UDS transport.
- **Tracers:** The failure occurs before tracer runtime behavior. This
  explains why both Python and PHP were affected.
- **Shared lib-init path:** All language init images use the shared
  [`copy-lib.sh`](https://github.com/DataDog/libdatadog-build/blob/main/scripts/lib-injection/copy-lib.sh)
  from `libdatadog-build`. This is the common copy path across languages.

The investigation found no recent change to `copy-lib.sh` or its Dockerfile
that aligned with the incident. The July 2026 BusyBox-to-Toybox migration
([libdatadog-build #235](https://github.com/DataDog/libdatadog-build/pull/235))
made the base image smaller. Its memory-constrained copy follow-up
([libdatadog-build #237](https://github.com/DataDog/libdatadog-build/pull/237))
predates the incident by several months. The available evidence does not link
either change to the incident.

## Unknowns

- What payload or environmental change made `256Mi` insufficient.
- Whether the twelve PHP profiling failures were also OOM failures.
- What caused the three Kubernetes API-server connectivity failures.
- How the current image differs from a pre-incident passing image in unpacked
  size, file count, and peak copy memory.
- Whether `256Mi` is a supported product constraint.

## Temporary test deactivation

Do not add component-version-specific declarations because the failures move
between matrix cells.

The temporary declarations tracked by
[INPLAT-1393](https://datadoghq.atlassian.net/browse/INPLAT-1393) are:

- Mark `test_k8s_lib_injection` for Python and PHP only in
  `K8S_LIB_INJECTION` and `K8S_LIB_INJECTION_UDS`. Use a decorator because the
  same test also runs in no-admission-controller scenarios.
- Mark the PHP positive-profiling tests in
  `K8S_LIB_INJECTION_PROFILING_ENABLED` and
  `K8S_LIB_INJECTION_PROFILING_OVERRIDE` through the PHP manifest. These
  declarations are precautionary: the nightly failure pattern is consistent
  with OOM, but no profiling artifact has confirmed it.
- Mark the PHP profiling-disabled test through the manifest while both
  positive controls are deactivated. Without an active positive control,
  missing profiling data cannot prove that suppression works.
- Do not mark Operator, no-admission-controller, AppSec, Spark, or HTTPS-egress
  tests.

## Next actions

1. Compare a pre-incident passing image digest with the current digest. Measure
   unpacked package size, file count, and peak memory during copy.
2. Run `copy-lib.sh` outside Kubernetes with the exact failing digest under
   `256Mi`, `320Mi`, `384Mi`, and `512Mi` limits.
3. Run the PHP profiling-enabled and profiling-override scenarios with
   `512Mi`, or inspect a failing profiling artifact for `OOMKilled`.
4. Decide whether `256Mi` is a supported product constraint. If it is, reduce
   the copy-time memory requirement or payload size. If it is not, update the
   system-tests scenario configuration.
5. Change `copy-lib.sh` recovery so an interrupted copy cannot remove the
   library and then report success.
