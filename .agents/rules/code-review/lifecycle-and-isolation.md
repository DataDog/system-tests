### LIFE-001: Setup Methods Must Not Fail
- Severity: P0
- Flag: `setup_*` methods must not assert or raise to validate expected test data. Store results and validate them in `test_*`. One setup failure stops the scenario.
- Detect: A setup method asserts, explicitly raises, or calls a validation helper that raises when expected test data is absent.
- Not when: A required setup action fails unexpectedly, or a prerequisite must succeed before later setup actions can run.
- Ref: [Add a new test](../../../docs/edit/add-new-test.md), [Test flow](../../../docs/understand/test-flow.md)

### LIFE-002: Avoid fixed sleeps and unbounded waits
- Severity: P1
- Flag: Do not use `time.sleep()`, fixed delays, or unbounded polling to wait for end-to-end data. Use `agent_interface_timeout` or `library_interface_timeout` for the general post-setup flush window. Use a bounded condition wait in `setup_*` when a specific condition must be observed before teardown or before triggering a subsequent action.
- Detect: A setup or test uses a fixed sleep, polls without a deadline, or increases an arbitrary delay instead of waiting for an observable condition.
- Not when: The delay itself is the behavior under test and no observable condition can represent it.
- ✅ Configure the scenario flush timeout for general data collection, or use `interfaces.library.wait_for(condition, timeout=...)` for a specific condition.
- ❌ Use `time.sleep(30)` before assuming that traces or Remote Config are ready.
- Ref: [End-to-end scenario implementation](../../../utils/_context/_scenarios/_core/endtoend.py)

### LIFE-003: Wait for the reply that belongs to this action.
- Old_id: codex-16
- Severity: P0
- Flag: Match the trace, event, or acknowledgement to this request by its request id, or to this Remote Config change by its config version. Do not use one from an earlier request or an earlier config. Start watching before that request or config change, or a fast result is missed. If later code needs the new Remote Config, wait until the tracer is using it. "Received" only means the message arrived, and a test that only checks that arrival may stop there.
- Detect: The wait accepts a trace or event whose request id is from an earlier request. It accepts a Remote Config acknowledgement for an older config version. Watching starts after the request. The test sends traffic as soon as Remote Config says "received".
- Not when: The capture has only this request, or the earlier request is the control.
- ✅ Wait until the tracer uses the new Remote Config version before sending traffic. Note the start time before the weblog request, and keep only the trace with that request id.
- ❌ Send traffic as soon as Remote Config says "received". Note the start time after the weblog request.

### LIFE-004: Collect end-to-end data before teardown
- Old_id: codex-12
- Severity: P0
- Flag: Collect data and perform bounded waits in `setup_*`, while containers are running. Keep assertions in `test_*`, after teardown. When a setup wait observes data that the test will validate, store its result and let the test report the validation failure instead of asserting or raising from setup.
- Detect: An end-to-end `test_*` method waits for new interface data, or `setup_*` asserts that expected trace, event, or metric data arrived.
- Not when: The test is parametric, or the wait verifies an infrastructure prerequisite required to execute later setup actions safely.
- ✅ Store the response and wait result during setup, then assert and inspect the captured data in `test_*`.
- ❌ Poll for traces in `test_*` after the containers have stopped, or assert expected trace contents from `setup_*`.
- Ref: [End-to-end test flow](../../../docs/understand/test-flow.md#end-to-end-scenario), [Flushing default behavior](../../../docs/edit/flushing.md#default-behavior)
