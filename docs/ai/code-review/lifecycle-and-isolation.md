## 4. Setup Methods Must Not Fail

`setup_*` methods must never contain assertions, raise exceptions, or call code that can fail. They exist only for observability (trigger trace generation). If one fails, the entire scenario stops. Assertions belong in `test_*` methods.

- Ref: [add-new-test.md](mdc:docs/edit/add-new-test.md), [test-flow.md](mdc:docs/understand/test-flow.md)

## 5. Use Scenario-Level Timeouts, Not Test-Level Sleeps

Do not add `time.sleep()` or explicit waits inside `setup_` method in end-to-end scenarios. If a longer wait is needed, use the scenario parameters `agent_interface_timeout` or `library_interface_timeout` defined in `utils/_context/_scenarios/_core/endtoend.py`.

ID: codex-16

Title: Wait for the reply that belongs to this action.

Rule: Match the trace, event, or acknowledgement to this request by its request id, or to this Remote Config change by its config version. Do not use one from an earlier request or an earlier config. Start watching before that request or config change, or a fast result is missed. If later code needs the new Remote Config, wait until the tracer is using it. "Received" only means the message arrived, and a test that only checks that arrival may stop there. Skip this match when the capture has only this request, or when the earlier request is the control.

Why:  An old trace or event can make the test pass. A late start can drop a fast one. Traffic can leave while the tracer is still on the old Remote Config.

Detect: The wait accepts a trace or event whose request id is from an earlier request. It accepts a Remote Config acknowledgement for an older config version. Watching starts after the request. The test sends traffic as soon as Remote Config says "received".

Example: Bad: saw "received" for a new Remote Config version and sent traffic at once. The tracer was still on the old config. Good: wait until the tracer uses that config version, then send the traffic. Bad: the test notes the start time after the weblog request. Good: note the start time, then send the weblog request, and keep only the trace with that request id.

Evidence:

• https://github.com/DataDog/system-tests/pull/7782
• https://github.com/DataDog/system-tests/pull/7628#issuecomment-5501260850
• https://github.com/DataDog/system-tests/pull/7266
• https://github.com/DataDog/system-tests/pull/6954

ID: codex-12

Title: Collect end-to-end data before assertions start.

Rule: Follow https://github.com/DataDog/system-tests/blob/main/docs/understand/test-flow.md#end-to-end-scenario and https://github.com/DataDog/system-tests/blob/main/docs/edit/flushing.md#default-behavior. Collect data through scenario flush settings or a bounded condition wait in `setup_*`, while containers still run. Keep assertions about required data in `test_*`. An end-to-end `test_*` method must not wait for new data. Parametric tests are out of scope.

Why: End-to-end assertions run after the scenario stops its containers. A wait inside `test_*` cannot receive new data. A condition wait during setup can avoid stopping collection before required data arrives.

Detect: An end-to-end `test_*` polls for new events. A setup wait raises on missing data instead of leaving the assertion to `test_*`.

Example: Bad: `test_events` polls for 30 seconds after teardown. Good: set the scenario's `agent_interface_timeout` or `library_interface_timeout`, or use a bounded condition wait in `setup_*`. Then assert on captured data in `test_events`.

Evidence:

• https://github.com/DataDog/system-tests/pull/7764
• https://github.com/DataDog/system-tests/pull/7231#discussion_r3497333625
• https://github.com/DataDog/system-tests/pull/7231#discussion_r3499245001
