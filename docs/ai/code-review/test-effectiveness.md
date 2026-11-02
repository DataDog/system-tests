TEST-001: No Runtime Library Branching in Test Logic
flag: Tests must not use `if context.library == "python"` (or similar) to run different logic per language. Instead, create separate test methods and use manifests to activate the relevant one per library.
detect: <TODO_RMM>
not when: <TODO_RMM>
ie good: <TODO_RMM>
ie bad: <TODO_RMM>
ref: [Manifest](../../edit/manifest.md)

TEST-002: Do not reject valid output because of unrelated data.
flag: When checking one protocol flag, mask that bit and accept other bits the protocol allows, unless the whole field is under test. When checking one member of a list field, such as a `tracestate` vendor or an `x-datadog-tags` entry, find that member. Do not require a count or an order that the protocol does not define. When checking for redaction leaks, use a distinctive marker or the relevant parsed field so unrelated payload values cannot count as leaked input.
detect: A sampled-bit assertion requires exact flags `01`. A test requires `len(tracestate) == 1` or compares `x-datadog-tags` as a raw string. A redaction check searches an entire payload for a short marker such as `1234`.
not when: The whole field is under test.
ie good: For the sampled bit, accept `01` and `03` when the extra bit is allowed. Use `assert any(item.startswith("dd=") for item in tracestate)`. A timestamp containing `1234` must not count as leaked input.
ie bad: `assert len(tracestate) == 1`.

TEST-003: Do not treat missing data as proof that suppression works.
flag: Missing spans, logs, metrics, or events do not prove that a disabled feature works. The same test must also show that this data is present when the feature is enabled. Use the same SDK build and otherwise equivalent inputs. Observe that control on the same transport and capture path as the absence check. The control can be another run, a paired case, or an allowed subject.
detect: A test expects no spans, logs, metrics, or events, and no assertion shows that data when the feature is on. Its control bypasses the proxy or receiver used for the absence check. A new entry in `utils/scripts/activate_easy_wins/skip.yml` is a review signal for this case.
not when: <TODO_RMM>
ie good: An enabled control reaches the same receiver through the same proxy.
ie bad: Accept zero runtime metrics with metrics disabled and never show those metrics with metrics enabled. A control that sends straight to the Agent does not prove that the proxy forwards UDP.

TEST-004: Do not use private debug wording as the only proof.
flag: Assert SDK behavior through its result, captured output, or a documented log contract. Do not use an undocumented debug message as the only proof that the behavior occurred.
detect: The assertion searches for a debug string that no documented contract defines.
not when: The log wording is part of a documented contract.
ie good: Inspect the captured span.
ie bad: Prove a span exists by finding `span created` in private debug logs.

TEST-005: Read trace payloads through the protocol-agnostic helpers.
flag: A test of behavior that does not depend on the trace encoding must give the same result for v0.4, v0.5, and v1.0 payloads. Compare trace IDs with `trace_id_equals()`, read the sampling priority with `get_sampling_priority()`, and filter intake requests with `interfaces.library.trace_paths`. Use `is_same_boolean()` only when the contract accepts `True`, `1`, and `"true"` as the same value. A test of the wire format itself must check the exact fields and types of its encoding.
detect: A test that is not about the encoding compares raw fields, as in `span["trace_id"] == expected` or `meta[key] == "true"`. A test reads a sampling priority field directly. A path filter lists only `/v0.4/traces` or `/v0.5/traces`.
not when: The test is explicitly validating the wire format itself.
ie good: `assert span.trace_id_equals(int(expected_id))`.
ie bad: `assert span["trace_id"] == int(expected_id)`.

TEST-006: Keep library branches out of assertions, not out of setup.
flag: A condition on the library must not change what a `test_*` method asserts. A `setup_*` method may use library-specific code when every branch triggers the same specified behavior.
detect: Flag a condition on `context.library` that changes an assertion, in a `test_*` method or in a helper that only assertions use. Do not flag a read of `context.library` that leaves the assertion unchanged. Do not flag a `setup_*` branch that only changes which request triggers the behavior.
not when: A read of `context.library` leaves the assertion unchanged, or a `setup_*` branch only changes which request triggers the behavior.
ie good: `setup_metrics` calls an exception endpoint only for .NET, so that the exception metric exists, and the test asserts the same values for every library.
ie bad: `assert count == (2 if context.library == "java" else 1)`.
ref: [PR review guidelines](../../../.cursor/rules/pr-review.mdc)

TEST-007: Do not set the value the test expects.
flag: Do not write the expected tag, code, or exporter result in the test app. The SDK must produce it. The assertion may name the value it expects. It must read that value from SDK output..
detect: The app adds `runtime-id` or another tag the SDK must produce. It copies SDK result codes into its own map. It forces an exporter that the configuration already selects.
not when: <TODO_RMM>
ie good: The tracer sets `runtime-id`, and the test asserts it on the captured span.
ie bad: The app sets `runtime-id` on the span, and the test asserts that tag.

TEST-008: Check mocks against the real service contract.
flag: When the test uses a fake Agent or backend, its request and response must match the real service. Check that shape in the spec, the real code, or a real capture. Do not copy the expected JSON from the fake. A deliberately broken response belongs only in the test of that error.
detect: The self-test imports every expected value from the fake. The fake returns a bare body where the real service uses an envelope. The fake sends config for a product the client did not ask for.
not when: The test intentionally validates a deliberately broken response.
ie good: Return the real backend envelope under `data.attributes`, and derive the check from the real contract.
ie bad: Return the flag config as the whole body and make the self-test expect that same body.
