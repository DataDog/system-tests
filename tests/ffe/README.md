# FFE (Feature Flags & Experimentation) Tests

This directory contains system tests for the Feature Flags & Experimentation (FFE) functionality.

## Test Files

| File | Description |
|------|-------------|
| `test_dynamic_evaluation.py` | Dynamic flag evaluation via Remote Config |
| `test_exposures.py` | Flag exposure tracking and reporting |
| `test_flag_eval_metrics.py` | Evaluation metrics (OTel counter) |

## Running FFE Tests

```bash
./run.sh FEATURE_FLAGGING_AND_EXPERIMENTATION --library <language>
```

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
