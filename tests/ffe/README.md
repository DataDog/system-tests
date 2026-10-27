# FFE (Feature Flags & Experimentation) Tests

This directory contains system tests for the Feature Flags & Experimentation (FFE) functionality.

## Test Files

| File | Description |
|------|-------------|
| `test_dynamic_evaluation.py` | Dynamic flag evaluation via Remote Config |
| `test_exposure_egress.py` | Shared exposure cache and payload contract across Agent, sidecar, and direct egress |
| `test_exposures_datadog_agent.py` | Flag exposure tracking and reporting through the Datadog Agent |
| `test_flag_eval_metrics.py` | Evaluation metrics (OTel counter) |
| `test_flag_eval_evp.py` | Server-side EVP flagevaluation payloads, aggregation, and bounds |
| `test_evaluation_telemetry_opt_out.py` | Per-subject evaluation telemetry opt-out, default-off behavior, and unchanged exposures |

## Canonical parametric fixtures

The parametric evaluation suite reads the checked-in snapshot under
`tests/parametric/test_ffe/ffe-system-test-data`. Its upstream source and exact
commit are recorded in `SOURCE.md` inside that directory.

Change shared evaluator cases in
[`DataDog/ffe-system-test-data`](https://github.com/DataDog/ffe-system-test-data)
first, then refresh the snapshot:

```bash
python3 utils/scripts/update_ffe_fixtures.py --ref <branch-tag-or-commit>
```

The updater imports `ufc-config.json` and `evaluation-cases/*.json` only. Ordinary
test runs use those checked-in files without submodules or network access. A
weekly/manual workflow opens a signed draft PR when their contents change and
leaves any existing fixture update PR untouched. Review and resolve newly exposed
SDK failures before merging an update.

Dynamic evaluation checks each case's value, reason, and explicit error code.
`Test_Feature_Flag_Split_Features` additionally checks every canonical case with
`result.features` against the public exposure-hook callback and actual exposure
and evaluation payloads received by the parametric test agent. Exact maps detect
missing values, extra keys, destination leaks, and boolean/number coercion while
preserving JSON numeric equivalence. This covers false, zero, empty strings,
first-valid-key selection, and selected-allocation isolation. For `doLog=false`,
selected metadata is checked separately and exposure delivery must stay absent.

The destination test currently runs with Java's `1.69.0-SNAPSHOT` SDK and later;
other clients are marked `incomplete_test_app` until they capture their public
hook output. Their baseline evaluation cases continue to run. The Java harness
loads the optional hook API only when this test enables capture, so older SDKs
can still compile and run baseline tests. Unsupported clients skip this slower
delivery test before container setup. An opt-in test-agent app factory registers
the FFE intake routes missing from the pinned agent image and records their
original payloads. This proves local delivery, not Datadog intake or production.

Cases with optional `capabilities` still run their baseline `result`; enabling
capability-specific provider options requires separate harness support.
Remote Configuration tests and the mocked agentless backend read the same UFC.
Serial-ID metadata and span-enrichment tests select their flag definitions from
the shared corpus using their dedicated evaluation-case files. Their integration
harnesses retain trace construction and metadata assertions; no separate local
configuration copies are needed.

## Running FFE Tests

Standalone rules-configuration helpers are covered in `tests/parametric/test_ffe/test_rules_configuration.py` (Node.js only for now). These tests use `dd-trace/openfeature/rules-based` in a fresh process without initializing a tracer or provider, fetch protobuf over HTTP, and validate the portable wire output, channel credentials, typed errors, deadlines and cancellation during headers/body delivery, transport failures, invalid options, and redirect protection. They do not initialize a browser SDK or contact Datadog.

These tests report to [Offline initialization and portable configuration helpers (#562)](https://feature-parity.us1.prod.dog/?feature=562). Current coverage is limited to Node's rules-based fetching and serialization; precomputed helpers and provider offline initialization are not covered here.

With Docker and the Python 3.12 runner installed:

```bash
PYTEST_XDIST_AUTO_NUM_WORKERS=1 TEST_LIBRARY=nodejs ./run.sh PARAMETRIC tests/parametric/test_ffe/test_rules_configuration.py
```

Until the helpers are released, use a master build as described in the [custom Node.js binary instructions](../../docs/execute/binaries.md#nodejs-library). The Node manifest currently targets master's `7.0.0-pre` development version; update that gate to the actual release version once published.

The protobuf fixture `tests/parametric/test_ffe/rules-wire.json` comes from `openfeature-js-client/packages/browser/test/data/rules-v1-wire.json`. The test checks serialization without evaluating flags or depending on a browser package.

```bash
./run.sh FEATURE_FLAGGING_AND_EXPERIMENTATION --library <language>
```

## Per-subject evaluation telemetry opt-out

All four test classes report under [#649: Per-subject evaluation telemetry opt-out](https://feature-parity.us1.prod.dog/#/?feature=649).

The [customer solutions document](https://docs.google.com/document/d/15rai-S0NmGO2sKsMgy6cGf4963Y--9qdEfAj5MiytUg/edit)
describes the customer capability. The implemented name is `dd_evaluation_telemetry_opt_out`.
The [explicit scope decision](https://github.com/DataDog/dd-sdk-ios/pull/3305#discussion_r4326232944)
preserves experiment exposures, and the
[attribute decision](https://github.com/DataDog/dd-trace-go/pull/5611#discussion_r4307380659)
retains the control in targeting and exposure attributes.

Candidate SDK implementations must pass the applicable local checks before delivery.
Released-version CI activation is a separate step. Both scenarios are excluded from the default
`all`, `end_to_end`, and `tracer_release` groups. They remain selectable by name or through the `ffe` group.
When activating released versions in manifests, restore the default scenario groups too.
Otherwise tracer CI that selects only `tracer_release` does not run these tests.
Manifests mark unsupported SDK versions as expected failures; this does not prevent their setup from running.
Use a local candidate SDK and force these tests to validate unreleased changes:

```bash
./run.sh FEATURE_FLAGGING_EVALUATION_TELEMETRY_OPT_OUT tests/ffe/test_evaluation_telemetry_opt_out.py \
  -F tests/ffe/test_evaluation_telemetry_opt_out.py
./run.sh FEATURE_FLAGGING_EVALUATION_TELEMETRY_OPT_OUT_DISABLED tests/ffe/test_evaluation_telemetry_opt_out.py \
  -F tests/ffe/test_evaluation_telemetry_opt_out.py
```

The enabled scenario sets `DD_FEATURE_FLAGS_EVALUATION_TELEMETRY_PER_SUBJECT_OPT_OUT_ENABLED=true`.
The disabled scenario leaves the setting absent. Both use the same requests.

| Context value | Enabled | Disabled |
| --- | --- | --- |
| Boolean `true` | No evaluation telemetry | Evaluation telemetry remains |
| Boolean `false`, missing, `null`, string `"true"`, or number `1` | Evaluation telemetry remains | Evaluation telemetry remains |
| Wrong-case key or legacy `dd_telemetry_opt_out` key | Evaluation telemetry remains | Evaluation telemetry remains |

The SDK reads the attribute on every evaluation. A subject stays opted out only while each evaluation context carries it.
Set the attribute in the context supplied to the evaluation call.
These tests do not cover opt-outs added by application hooks; SDK behavior differs for those hooks.

Separate tests check exact EVP counts, evaluation metric presence, and automatic trace annotations.
Metric checks accept delta exports and repeated cumulative exports. Opted-out flags must have no nonzero metric points.
Each test includes allowed subjects as positive controls.
Mixed subjects evaluate the same flag to detect a flag-scoped opt-out decision.
EVP counts match both the flag and the subject's raw or hashed targeting key.
Shared-flag subjects receive the same value from distinct fixture allocations.
Metric assertions use the allocation tags to check each subject separately, without adding subject tags to metrics.
One rule targets the opt-out attribute to verify that it remains available for evaluation.
One subject opts out, then removes the attribute; later evaluations must emit telemetry again.
Those two phases use distinct allocation tags with the same flag value, so resumed metrics cannot hide an earlier leak.
Missing flags test suppression on the error path, return the application default, and produce no exposures.
Configured flags must return the same flag value for every request.
Exposures must retain their context attributes and ordinary deduplication for an unchanged context.
After an attribute changes, exposure deduplication can differ between SDKs; these tests do not check it.
Validation reads final captures after the scenario stops its application and drains the Agent.
Remote Configuration and evaluation-request errors are reported during validation, without aborting the remaining setups.

PHP coverage is deferred until its OpenFeature test-app foundation is available.
.NET EVP coverage requires a tracer release containing [dd-trace-dotnet#9351](https://github.com/DataDog/dd-trace-dotnet/pull/9351).
For older candidates without that producer, exclude the EVP class with `-k 'not EVP'`.
Browser and mobile SDKs are outside this server harness and retain their repository integration tests.

### Release activation and follow-up coverage

Replace each provisional manifest entry with the first released SDK version containing its opt-out implementation.
For Node.js, this must include [dd-trace-js#10776](https://github.com/DataDog/dd-trace-js/pull/10776); a merged PR is not a released version.
.NET needs a tracer release containing [dd-trace-dotnet#9426](https://github.com/DataDog/dd-trace-dotnet/pull/9426)
and a weblog using `Datadog.FeatureFlags.OpenFeature` 2.3.3 or later.
Its EVP class has a separate dependency on #9351. The tracer manifest does not gate the NuGet provider version.

These scenarios activate opt-out through the process environment only.
Coverage for other configuration sources, such as `application_monitoring.yaml`, is separate follow-up work.

### Local .NET candidate packages

Put the `Datadog.Trace` and `Datadog.FeatureFlags.OpenFeature` packages in `binaries/`.
Also supply the matching tracer archive (`datadog-dotnet-apm-<version>*.tar.gz`) or extracted tracer files.
For the `poc` weblog, pass exact NuGet version ranges through the Docker build arguments:

```bash
./build.sh dotnet -w poc --extra-docker-args \
  "--build-arg DD_TRACE_PACKAGE_VERSION=[<tracer-package-version>] --build-arg DD_OPENFEATURE_PACKAGE_VERSION=[<provider-package-version>]"
```

Brackets require that exact version. A plain version is a minimum; NuGet can select a higher version with warning NU1603.
Use unique candidate versions that are not published on nuget.org, so only `binaries/` can supply them.
Verify the resolved packages before reporting local validation. These arguments do not select the installed tracer binary.
The `uds` weblog does not support these build arguments or the local package source.

## Test-contract self-tests

The self-tests in `tests/test_the_test/test_ffe_tests.py` and
`tests/test_the_test/test_ffe_evaluation_telemetry_opt_out.py` validate the FFE assertions
using synthetic captures. They do not run SDKs or contact an intake. They are part of
the `TEST_THE_TEST` scenario, which runs on every PR. With the Python 3.12 runner
environment installed, run them explicitly:

```bash
./run.sh TEST_THE_TEST tests/test_the_test/test_ffe_tests.py tests/test_the_test/test_ffe_evaluation_telemetry_opt_out.py
```
Framework mock-backend and lifecycle tests stay in `tests/test_the_test/`.

---

# Eval Metrics Implementation Guide

This section captures lessons learned from implementing flag evaluation metrics in dd-trace-py to help accelerate implementations in other SDKs.

## Quick Start

### 1. Local Testing is Much Faster Than CI

**CI takes 1+ hour. Local testing takes ~2 minutes.**

Run FFE tests locally:
```bash
./run.sh FEATURE_FLAGGING_AND_EXPERIMENTATION --library <language> -k "test_ffe_eval"
```

Example for Python:
```bash
./run.sh FEATURE_FLAGGING_AND_EXPERIMENTATION --library python -k "test_ffe_eval"
```

### 2. Loading SDK from S3 for Local Testing

For Python, create `binaries/python-load-from-s3` with the commit SHA:
```bash
echo "<commit-sha>" > binaries/python-load-from-s3
```

Check if the wheel is on S3 by verifying the "Upload wheels to S3" job passed in the SDK's CI.

---

## Implementation Checklist

### SDK Changes Required

1. **Implement `feature_flag.evaluations` OTel counter metric**
   - Emitted on every flag evaluation via OpenFeature hooks
   - Use a **Finally hook** (not in evaluate()) to capture type conversion errors

2. **Required tags:**
   - `feature_flag.key` — the flag key
   - `feature_flag.result.variant` — the resolved variant
   - `feature_flag.result.reason` — lowercase (e.g., `targeting_match`, `error`, `default`, `disabled`, `static`, `split`)
   - `feature_flag.result.allocation_key` — only when present and non-empty
   - `error.type` — only on error, lowercase (e.g., `flag_not_found`, `type_mismatch`, `parse_error`, `provider_not_ready`)

3. **Cross-tracer consistency requirements:**
   - Return `PROVIDER_NOT_READY` (not `GENERAL`) when no config is loaded
   - Use `"unknown"` (not empty string) as fallback for missing reason
   - Use raw lowercase error codes directly (no conversion functions)

### System Tests Changes Required

1. **Add OTel OTLP metrics exporter to weblog Dockerfiles**

   For Python, add to each weblog Dockerfile:
   ```dockerfile
   RUN pip install opentelemetry-exporter-otlp-proto-http
   ```

2. **Enable tests in manifest**

   In `manifests/<language>.yml`, change:
   ```yaml
   tests/ffe/test_flag_eval_metrics.py: missing_feature
   ```
   to:
   ```yaml
   tests/ffe/test_flag_eval_metrics.py: <version>
   ```

---

## Test Coverage

The system tests cover:

### Resolution Reasons (5 tests)
| Reason | Test | Scenario |
|--------|------|----------|
| `static` | `Test_FFE_Eval_Metric_Basic` | No rules, no shards (catch-all) |
| `targeting_match` | `Test_FFE_Eval_Reason_Targeting` | Targeting rules match context |
| `split` | `Test_FFE_Eval_Reason_Split` | 50/50 shard-based rollout |
| `default` | `Test_FFE_Eval_Reason_Default` | Rules don't match |
| `disabled` | `Test_FFE_Eval_Reason_Disabled` | Flag is disabled |

### Error Codes (5 tests)
| Error Code | Test | Trigger |
|------------|------|---------|
| `flag_not_found` | `Test_FFE_Eval_Config_Exists_Flag_Missing` | Config exists, flag missing |
| `type_mismatch` | `Test_FFE_Eval_Metric_Type_Mismatch` | Request boolean from string flag |
| `parse_error` | `Test_FFE_Eval_Metric_Parse_Error_Invalid_Regex` | Invalid regex pattern in condition |
| `parse_error` | `Test_FFE_Eval_Metric_Parse_Error_Variant_Type_Mismatch` | Variant value doesn't match declared type |
| `provider_not_ready` | `Test_FFE_Eval_No_Config_Loaded` | No config loaded |

### Other Tests
- `Test_FFE_Eval_Metric_Count` — Multiple evaluations produce correct count
- `Test_FFE_Eval_Metric_Different_Flags` — Different flags get separate series
- `Test_FFE_Eval_Metric_Numeric_To_Integer` — Numeric to integer conversion
- `Test_FFE_Eval_Targeting_Key_Optional` — Targeting key is optional
- `Test_FFE_Eval_Nested_Attributes_Ignored` — Nested attributes silently ignored (OF.3)
- `Test_FFE_Eval_Lowercase_Consistency` — All tag values are lowercase

---

## UFC Fixture Format

### Important: Split Fixture Format

The `totalShards` field must be **inside each shard object**, not at the allocation level:

```python
# CORRECT format for split/shard-based allocation
"splits": [
    {
        "variationKey": "on",
        "shards": [
            {
                "salt": "test-salt",
                "totalShards": 10000,  # Inside shard object
                "ranges": [{"start": 0, "end": 5000}],
            }
        ],
    },
    {
        "variationKey": "off",
        "shards": [
            {
                "salt": "test-salt",
                "totalShards": 10000,
                "ranges": [{"start": 5000, "end": 10000}],
            }
        ],
    },
]
```

**Note:** A single variation covering 100% (0-10000) returns `STATIC`, not `SPLIT`. You need multiple variations with different shard ranges for a true `SPLIT` reason.

---

## Debugging Tips

### Check Weblog Logs
```bash
cat logs_feature_flagging_and_experimentation/docker/weblog/stdout.log
cat logs_feature_flagging_and_experimentation/docker/weblog/stderr.log
```

### Check Agent Metrics
The tests use `interfaces.agent.get_metrics()` to retrieve metrics from the agent.

### Run Single Test
```bash
./run.sh FEATURE_FLAGGING_AND_EXPERIMENTATION --library python -k "Test_FFE_Eval_Reason_Split"
```

---

## Common Issues

### 1. Test returns `parse_error` instead of expected reason
- Check UFC fixture format (especially `totalShards` placement)
- Verify the fixture matches the canonical `ffe-system-test-data/ufc-config.json` format

### 2. Test returns `static` instead of `split`
- Need multiple variations with different shard ranges
- Single variation covering 100% returns `static`

### 3. Metrics not found
- Verify OTel exporter is installed in weblog
- Check `DD_METRICS_OTEL_ENABLED=true` is set in scenario
- Verify the metric export interval (10s default)

### 4. CI takes too long
- Run locally first: `./run.sh FEATURE_FLAGGING_AND_EXPERIMENTATION --library <lang> -k "test_ffe_eval"`
- Only push to CI when local tests pass

---

## Reference PRs

### Python Implementation
- **dd-trace-py**: [PR #17029](https://github.com/DataDog/dd-trace-py/pull/17029)
- **system-tests**: [PR #6545](https://github.com/DataDog/system-tests/pull/6545)

### Go Implementation (reference)
- **dd-trace-go**: [PR #4489](https://github.com/DataDog/dd-trace-go/pull/4489)
- **Add allocation_key**: [PR #4515](https://github.com/DataDog/dd-trace-go/pull/4515)

---

## Workflow Summary

1. **Implement metrics in SDK** following the Go reference implementation
2. **Create system-tests branch** off `main`
3. **Add OTel exporter** to weblog Dockerfiles
4. **Enable tests** in manifest file
5. **Run locally** with `./run.sh` to iterate quickly
6. **Push to CI** only when local tests pass
