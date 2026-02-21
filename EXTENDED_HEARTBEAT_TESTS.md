# System Tests - app-extended-heartbeat Telemetry Tests

## Implementation Summary

**Date**: 2026-02-18
**File**: `tests/parametric/test_telemetry.py`
**Test Class**: `Test_ExtendedHeartbeat`
**Lines**: 1253-1515

## Test Coverage

### Existing Tests (Already Implemented)

1. **`test_app_extended_heartbeat_sent`** (lines 1268-1293)
   - **Purpose**: Verify app-extended-heartbeat events are sent with configuration data
   - **Setup**: Fast intervals (0.1s heartbeat, 0.5s extended)
   - **Validation**: Event exists and contains at least one of: configuration, dependencies, integrations

2. **`test_app_extended_heartbeat_interval`** (lines 1304-1339)
   - **Purpose**: Verify extended heartbeat respects configured interval
   - **Setup**: Fast intervals (0.1s heartbeat, 0.3s extended)
   - **Validation**: Interval timing is within 50% margin (0.15s - 0.45s)

### New Tests Added

3. **`test_extended_heartbeat_payload_content`** (lines 1350-1396)
   - **Purpose**: Validate payload structure and field types
   - **Setup**: Fast intervals (0.1s heartbeat, 0.5s extended)
   - **Validation**:
     - Required fields exist: `configuration`, `dependencies`, `integrations`
     - All fields are arrays
     - At least one field contains data
     - Item structure validation: configuration items have `name`, dependencies have `name`, integrations have `name`

4. **`test_extended_heartbeat_matches_app_started`** (lines 1407-1457)
   - **Purpose**: Verify data consistency between app-started and app-extended-heartbeat
   - **Setup**: Fast intervals (0.1s heartbeat, 0.5s extended)
   - **Validation**:
     - Configuration keys match between events
     - Dependencies (name, version) match between events
     - Integrations (by name) match between events

5. **`test_extended_heartbeat_excludes_products_and_install_signature`** (lines 1467-1487)
   - **Purpose**: Verify app-extended-heartbeat excludes app-started-only fields
   - **Setup**: Fast intervals (0.1s heartbeat, 0.5s extended)
   - **Validation**: Payload does NOT contain: `products`, `install_signature`, `error`, `additional_payload`

6. **`test_extended_heartbeat_default_interval`** (lines 1498-1514)
   - **Purpose**: Verify default 24-hour interval prevents immediate emission
   - **Setup**: Regular heartbeat (0.1s), NO extended heartbeat interval set (defaults to 24h)
   - **Validation**: No extended heartbeat events appear within 2 seconds

## Test Design Patterns

### Timing Strategy
- All tests use **fast intervals** for efficient testing (0.3s - 0.5s instead of 24 hours)
- Default interval test uses **no override** to test actual default behavior
- Sleep times allow for 2-3 intervals to ensure events arrive

### Parametric Testing
- All tests decorated with `@pytest.mark.parametrize("library_env", [...])`
- Tests run across all SDK languages: Go, Java, .NET, C++, PHP, Ruby, Rust, Python, Node.js
- Environment variables passed via `library_env` parameter

### Data Validation Approach
- **Existence checks**: Fields must be present in payload
- **Type validation**: Arrays must be arrays, not nulls or other types
- **Content validation**: At least some data should exist (not all empty)
- **Structure validation**: Items in arrays have required fields (e.g., `name`)
- **Consistency validation**: Data matches between app-started and extended-heartbeat

### Error Messages
- All assertions include descriptive error messages
- Error messages include actual vs expected values
- Lists actual payload keys when validation fails

## SDK Language Coverage

The tests are designed to run parametrically across all supported languages:

| Language   | Expected Status | Notes |
|-----------|----------------|-------|
| Go         | ✓ Pass         | Should pass all tests |
| Java       | ✓ Pass         | Should pass all tests |
| .NET       | ✓ Pass         | Should pass all tests |
| C++        | ⚠ Partial      | May not implement extended heartbeat yet |
| PHP        | ✓ Pass         | Should pass all tests |
| Ruby       | ✓ Pass         | Should pass all tests |
| Rust       | ⚠ Partial      | May not implement extended heartbeat yet |
| Python     | ✓ Pass         | Should pass all tests |
| Node.js    | ✓ Pass         | Should pass all tests |

## API Reference

**Specification**: `/Users/ayan.khan/Code/instrumentation-telemetry-api-docs/GeneratedDocumentation/ApiDocs/v2/SchemaDocumentation/Schemas/app_extended_heartbeat.md`

### Expected Event Structure
```json
{
  "request_type": "app-extended-heartbeat",
  "payload": {
    "configuration": [
      {
        "name": "DD_TRACE_AGENT_URL",
        "origin": "env_var",
        "value": "http://localhost:9126"
      }
    ],
    "dependencies": [
      {
        "name": "express",
        "version": "4.17.1"
      }
    ],
    "integrations": [
      {
        "name": "express",
        "version": "4.17.1",
        "enabled": true,
        "auto_enabled": true
      }
    ]
  }
}
```

### Key Differences from app-started

**Included in both**:
- `configuration` (array)
- `dependencies` (array)
- `integrations` (array)

**Included ONLY in app-started**:
- `products` (e.g., appsec, profiler)
- `install_signature` (installation metadata)
- `error` (startup errors)
- `additional_payload` (SDK-specific data)

## Running the Tests

### Run all extended heartbeat tests
```bash
pytest tests/parametric/test_telemetry.py::Test_ExtendedHeartbeat -v
```

### Run a specific test
```bash
pytest tests/parametric/test_telemetry.py::Test_ExtendedHeartbeat::test_extended_heartbeat_payload_content -v
```

### Run for a specific language
```bash
TEST_LIBRARY=nodejs pytest tests/parametric/test_telemetry.py::Test_ExtendedHeartbeat -v
```

## Common Failure Scenarios

### Timing Issues
**Symptom**: Tests timeout waiting for events
**Cause**: SDK not emitting events at configured interval
**Fix**: Verify `DD_TELEMETRY_EXTENDED_HEARTBEAT_INTERVAL` env var is respected

### Missing Fields
**Symptom**: `Missing configuration field` assertion
**Cause**: SDK not including required fields in payload
**Fix**: Ensure SDK includes `configuration`, `dependencies`, `integrations` arrays (can be empty)

### Data Mismatch
**Symptom**: `Configuration keys should match` assertion
**Cause**: Data differs between app-started and extended-heartbeat
**Fix**: Ensure both events use same data source for configuration/dependencies/integrations

### Excluded Fields Present
**Symptom**: `'products' should not be in extended heartbeat payload`
**Cause**: SDK incorrectly includes app-started-only fields
**Fix**: Remove `products`, `install_signature`, `error`, `additional_payload` from extended heartbeat

### Default Interval Not Respected
**Symptom**: `Extended heartbeat should not fire within 2s`
**Cause**: SDK defaults to short interval instead of 24 hours
**Fix**: Verify default `DD_TELEMETRY_EXTENDED_HEARTBEAT_INTERVAL` is 86400 seconds (24 hours)

## Feature Tracking

**Feature ID**: 77
**Feature Parity Link**: https://feature-parity.us1.prod.dog/#/?feature=77
**Owner**: sdk_capabilities

## Next Steps

1. **Run tests across all languages** to identify implementation gaps
2. **Document language-specific failures** in this file
3. **Create GitHub issues** for SDKs that fail tests
4. **Update feature parity dashboard** with test results
5. **Verify SDK fixes** by re-running tests

## Related Tests

- `Test_TelemetryHeartbeat` - Regular heartbeat tests (lines 818-916)
- `Test_TelemetryMetrics` - Metrics telemetry tests (lines 918-1018)
- `Test_AppStarted` - App-started event tests (if exists)

## Implementation Notes

- Tests follow existing patterns in `test_telemetry.py`
- Use `test_agent.wait_for_telemetry_event()` for reliable event retrieval
- Use `test_agent.telemetry(clear=False)` to inspect all events
- Use `test_agent._get_telemetry_event(event, event_name)` to filter events
- All tests use `with test_library.dd_start_span("test")` to ensure library is active
