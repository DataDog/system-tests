### LIFE-001: Setup Methods Must Not Fail
- Severity: P0
- Flag: `setup_*` methods must not assert or raise to validate expected test data. Store results and validate them in `test_*`. One setup failure stops the scenario.
- Detect: A setup method asserts, explicitly raises, or calls a validation helper that raises when expected test data is absent.
- Not when: A required setup action fails unexpectedly, or a prerequisite must succeed before later setup actions can run.
- ❌ Example:
  ```python
  def setup_login(self):
      self.r = weblog.post("/login", data={"user": "test"})
      assert "session" in self.r.cookies
  ```
- ✅ Use instead:
  ```python
  def setup_login(self):
      self.r = weblog.post("/login", data={"user": "test"})

  def test_login(self):
      assert "session" in self.r.cookies
  ```
- Ref: [Add a new test](../../../docs/edit/add-new-test.md), [Test flow](../../../docs/understand/test-flow.md)

### LIFE-002: Avoid fixed sleeps and unbounded waits
- Severity: P1
- Flag: Do not use `time.sleep()`, fixed delays, or unbounded polling to wait for end-to-end data. Use `agent_interface_timeout` or `library_interface_timeout` for the general post-setup flush window. Use a bounded condition wait in `setup_*` when a specific condition must be observed before teardown or before triggering a subsequent action.
- Detect: A setup or test uses a fixed sleep, polls without a deadline, or increases an arbitrary delay instead of waiting for an observable condition.
- Not when: The delay itself is the behavior under test and no observable condition can represent it.
- ❌ Example: a fixed delay before the next action, hoping the data is ready.
  ```python
  def setup_second_request(self):
      self.first = weblog.get("/session/new")
      time.sleep(10)
      self.second = weblog.get("/session/check")
  ```
- ✅ Use instead: wait for the condition, with a deadline.
  ```python
  def setup_second_request(self):
      self.first = weblog.get("/session/new")
      interfaces.library.wait_for(self._has_session_trace, timeout=10)
      self.second = weblog.get("/session/check")
  ```
  For the general flush after setup, configure `library_interface_timeout` or `agent_interface_timeout` on the scenario.
- Ref: [End-to-end scenario implementation](../../../utils/_context/_scenarios/_core/endtoend.py)

### LIFE-003: Wait for the reply that belongs to this action.
- Old_id: codex-16
- Severity: P0
- Flag: Match the trace, event, or acknowledgement to this request by its request id, or to this Remote Config change by its config version. Do not use one from an earlier request or an earlier config. Start watching before that request or config change, or a fast result is missed. If later code needs the new Remote Config, wait until the tracer is using it. "Received" only means the message arrived, and a test that only checks that arrival may stop there.
- Detect: The wait accepts a trace or event whose request id is from an earlier request. It accepts a Remote Config acknowledgement for an older config version. Watching starts after the request. The test sends traffic as soon as Remote Config says "received".
- Not when: The capture has only this request, or the earlier request is the control.
- ❌ Example: traffic is sent as soon as Remote Config says "received", before the tracer uses the config.
  ```python
  def setup_blocking(self):
      rc.tracer_rc_state.set_config(*BLOCK_IP).apply(wait_for_acknowledged_status=False)
      self.r = weblog.get("/", headers={"X-Forwarded-For": "1.2.3.4"})
  ```
- ✅ Use instead: wait until the tracer has applied this config version, then send traffic, and keep only the trace of this request.
  ```python
  def setup_blocking(self):
      self.config = rc.tracer_rc_state.set_config(*BLOCK_IP).apply()
      self.r = weblog.get("/", headers={"X-Forwarded-For": "1.2.3.4"})

  def test_blocking(self):
      interfaces.library.assert_trace_exists(self.r)
  ```

### LIFE-004: Collect end-to-end data before teardown
- Old_id: codex-12
- Severity: P0
- Flag: Collect data and perform bounded waits in `setup_*`, while containers are running. Keep assertions in `test_*`, after teardown. When a setup wait observes data that the test will validate, store its result and let the test report the validation failure instead of asserting or raising from setup.
- Detect: An end-to-end `test_*` method waits for new interface data, or `setup_*` asserts that expected trace, event, or metric data arrived.
- Not when: The test is parametric, or the wait verifies an infrastructure prerequisite required to execute later setup actions safely.
- ❌ Example: the test waits for new data, but the containers have already stopped.
  ```python
  def setup_telemetry(self):
      self.r = weblog.get("/")

  def test_telemetry(self):
      interfaces.library.wait_for(self._has_app_started, timeout=30)
  ```
- ✅ Use instead: wait in setup and store the result, then assert in the test.
  ```python
  def setup_telemetry(self):
      self.r = weblog.get("/")
      self.started = interfaces.library.wait_for(self._has_app_started, timeout=30)

  def test_telemetry(self):
      assert self.started, "app-started was not received"
  ```
- Ref: [End-to-end test flow](../../../docs/understand/test-flow.md#end-to-end-scenario), [Flushing default behavior](../../../docs/edit/flushing.md#default-behavior)
