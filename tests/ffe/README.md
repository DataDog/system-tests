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
| `test_experimentation_opt_out.py` | Experimentation activation cutoff, configuration updates, holdout assignments, and exposure delivery |

## Running FFE Tests

```bash
./run.sh FEATURE_FLAGGING_AND_EXPERIMENTATION --library <language>
```

## Per-subject evaluation telemetry opt-out

All four test classes report under [#649: Per-subject evaluation telemetry opt-out](https://feature-parity.us1.prod.dog/#/?feature=649).

Candidate SDK implementations must pass the applicable local checks before delivery.
Released-version CI activation is a separate step. Both scenarios are excluded from the default
`all`, `end_to_end`, and `tracer_release` groups. They remain selectable by name or through the `ffe` group.
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
| Boolean `false`, missing, string `"true"`, or number `1` | Evaluation telemetry remains | Evaluation telemetry remains |

Separate tests check exact EVP counts, evaluation metric presence, and automatic trace annotations.
Metric checks accept delta exports and repeated cumulative exports. Opted-out flags must have no nonzero metric points.
Each test includes allowed subjects as positive controls.
Mixed subjects evaluate the same flag to detect a flag-scoped opt-out decision.
One rule targets the opt-out attribute to verify that it remains available for evaluation.
All requests must return the same flag value. Exposures must retain their ordinary deduplication and context attributes.
Validation reads final captures after the scenario stops its application and drains the Agent.
Remote Configuration and evaluation-request errors are reported during validation, without aborting the remaining setups.

PHP coverage is deferred until its OpenFeature test-app foundation is available.
.NET has no EVP evaluation producer. Exclude the EVP class when forcing its local runs with `-k 'not EVP'`.
Browser and mobile SDKs are outside this server harness and retain their repository integration tests.

## Per-subject experimentation opt-out

The tests report under [#650: Per-subject experimentation opt-out](https://feature-parity.us1.prod.dog/#/?feature=650).
They extend the [shared evaluator fixtures](https://github.com/DataDog/ffe-system-test-data/pull/52)
with Remote Config and captured EVP requests from a running SDK.
The first candidate is [Go future mode](https://github.com/DataDog/dd-trace-go/pull/5700), stacked on immediate mode.

| Scenario suffix | `DD_FEATURE_FLAGS_EXPERIMENTATION_OPT_OUT_MODE` | Expected behavior with a valid subject cutoff |
| --- | --- | --- |
| `DISABLED` | Unset | All allocations remain eligible. |
| `IMMEDIATE` | `immediate` | Skip exposure-logging allocations; continue ordinary delivery. |
| `FUTURE` | `future_experiments_only` | Keep older allocations; skip equal, newer, or unknown activation. |

All three scenarios enable the independent evaluation-telemetry opt-out control.
Each scenario starts a separate SDK process. The tests cover:

- Cutoff equality, offsets, fractions, unknown activation, invalid preferences, and absent preferences.
- Ordinary allocation fallback and the application default when no allocation matches.
- Concurrent subjects on one flag, with positive controls and repeated evaluations.
- Configuration edits that retain activation, followed by a new allocation with a new activation.
- Unchanged 10/90 holdout assignments for eligible subjects. This tests delivery, not downstream holdout analysis.
- Deduplicated exposures for eligible allocations, no exposures for skipped allocations, and independent evaluation telemetry.

Manifests keep this coverage provisional until supported SDK versions are known.
All three scenarios have explicit steps in `run-end-to-end.yml`.
They remain selectable by name or through `ffe`, but not through `all`, `end_to_end`, or `tracer_release`.
Setup errors are reported during validation without aborting the remaining setups.
Load the exact candidate Go commit with the [binary override](../../docs/execute/binaries.md),
then build the weblog and force the selected tests:

```bash
./build.sh golang -w net-http
./run.sh FEATURE_FLAGGING_EXPERIMENTATION_OPT_OUT_DISABLED tests/ffe/test_experimentation_opt_out.py \
  -F tests/ffe/test_experimentation_opt_out.py
./run.sh FEATURE_FLAGGING_EXPERIMENTATION_OPT_OUT_IMMEDIATE tests/ffe/test_experimentation_opt_out.py \
  -F tests/ffe/test_experimentation_opt_out.py
./run.sh FEATURE_FLAGGING_EXPERIMENTATION_OPT_OUT_FUTURE tests/ffe/test_experimentation_opt_out.py \
  -F tests/ffe/test_experimentation_opt_out.py
```

The current shared weblog returns the flag value, not OpenFeature error details.
Invalid-preference cases therefore check default delivery and no exposure.
The shared evaluator fixtures separately require `INVALID_CONTEXT`.

## Test-contract self-tests

The self-tests validate the FFE assertions using synthetic
captures. They do not run SDKs or contact an intake. With the Python 3.12 runner
environment installed, run them explicitly:

```bash
./run.sh FEATURE_FLAGGING_CONTRACT_TESTS tests/ffe/test_tests.py \
  tests/ffe/test_evaluation_telemetry_opt_out_contract.py tests/ffe/test_experimentation_opt_out_contract.py
```

This no-container scenario has no CI workflow or scenario-group membership.
Its tests do not run in `TEST_THE_TEST`, `DEFAULT`, or the FFE end-to-end scenarios.
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
- Verify the fixture matches `flags-v1.json` format in dd-trace-py

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
