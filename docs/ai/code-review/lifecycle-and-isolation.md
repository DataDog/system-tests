### LIFE-001: Setup Methods Must Not Fail
- Flag: `setup_*` methods must never contain assertions, raise exceptions, or call code that can fail. They exist only for observability (trigger trace generation). If one fails, the entire scenario stops. Assertions belong in `test_*` methods.
- Detect: <TODO_RMM>
- Not when: <TODO_RMM>
- ✅ <TODO_RMM>
- ❌ <TODO_RMM>
- Ref: [Add a new test](../../edit/add-new-test.md), [Test flow](../../understand/test-flow.md)

### LIFE-002: Use Scenario-Level Timeouts, Not Test-Level Sleeps
- Flag: Do not add `time.sleep()` or explicit waits inside `setup_` method in end-to-end scenarios. If a longer wait is needed, use the scenario parameters `agent_interface_timeout` or `library_interface_timeout` defined in `utils/_context/_scenarios/_core/endtoend.py`.
- Detect: <TODO_RMM>
- Not when: <TODO_RMM>
- ✅ <TODO_RMM>
- ❌ <TODO_RMM>
- Ref: [End-to-end scenario implementation](../../../utils/_context/_scenarios/_core/endtoend.py)

### LIFE-003: Wait for the reply that belongs to this action.
- old_id: codex-16
- Flag: Match the trace, event, or acknowledgement to this request by its request id, or to this Remote Config change by its config version. Do not use one from an earlier request or an earlier config. Start watching before that request or config change, or a fast result is missed. If later code needs the new Remote Config, wait until the tracer is using it. "Received" only means the message arrived, and a test that only checks that arrival may stop there.
- Detect: The wait accepts a trace or event whose request id is from an earlier request. It accepts a Remote Config acknowledgement for an older config version. Watching starts after the request. The test sends traffic as soon as Remote Config says "received".
- Not when: The capture has only this request, or the earlier request is the control.
- ✅ Wait until the tracer uses the new Remote Config version before sending traffic. Note the start time before the weblog request, and keep only the trace with that request id.
- ❌ Send traffic as soon as Remote Config says "received". Note the start time after the weblog request.

### LIFE-004: Collect end-to-end data before assertions start.
- old_id: codex-12
- Flag: Collect data through scenario flush settings or a bounded condition wait in `setup_*`, while containers still run. Keep assertions about required data in `test_*`. An end-to-end `test_*` method must not wait for new data.
- Detect: An end-to-end `test_*` polls for new events. A setup wait raises on missing data instead of leaving the assertion to `test_*`.
- Not when: The test is parametric.
- ✅ Set the scenario's `agent_interface_timeout` or `library_interface_timeout`, or use a bounded condition wait in `setup_*`. Then assert on captured data in `test_events`.
- ❌ `test_events` polls for 30 seconds after teardown.
- Ref: [End-to-end test flow](../../understand/test-flow.md#end-to-end-scenario), [Flushing default behavior](../../edit/flushing.md#default-behavior)
