## 2. No Runtime Library Branching in Test Logic

Tests must not use `if context.library == "python"` (or similar) to run different logic per language. Instead, create separate test methods and use manifests to activate the relevant one per library.

- Ref: [manifest.md](mdc:docs/edit/manifest.md)

ID: codex-09

Title: Do not reject valid output because of unrelated data.

Rule: When checking one protocol flag, mask that bit and accept other bits the protocol allows, unless the whole field is under test. When checking one member of a list field, such as a `tracestate` vendor or an `x-datadog-tags` entry, find that member. Do not require a count or an order that the protocol does not define. When checking for redaction leaks, use a distinctive marker or the relevant parsed field so unrelated payload values cannot count as leaked input.

Why: An allowed extra flag, an extra list member, another member order, or a coincidental substring can make a correct SDK fail the test.

Detect: A sampled-bit assertion requires exact flags `01`. A test requires `len(tracestate) == 1` or compares `x-datadog-tags` as a raw string. A redaction check searches an entire payload for a short marker such as `1234`.

Example: For the sampled bit, accept `01` and `03` when the extra bit is allowed. Bad: `assert len(tracestate) == 1`. Good: `assert any(item.startswith("dd=") for item in tracestate)`. A timestamp containing `1234` must not count as leaked input.

Evidence:

• https://github.com/DataDog/system-tests/pull/7939
• https://github.com/DataDog/system-tests/pull/7937
• https://github.com/DataDog/system-tests/pull/7372
• https://github.com/DataDog/system-tests/pull/8015

ID: cursor-03

Title: Do not treat missing data as proof that suppression works.

Rule: Missing spans, logs, metrics, or events do not prove that a disabled feature works. The same test must also show that this data is present when the feature is enabled. Use the same SDK build and otherwise equivalent inputs. Observe that control on the same transport and capture path as the absence check. The control can be another run, a paired case, or an allowed subject.

Why: A fully broken feature emits nothing. The absence check then stays green, and the test never notices the break.

Detect: A test expects no spans, logs, metrics, or events, and no assertion shows that data when the feature is on. Its control bypasses the proxy or receiver used for the absence check. A new entry in `utils/scripts/activate_easy_wins/skip.yml` is a review signal for this case.

Example: Bad: accept zero runtime metrics with metrics disabled, and never show those metrics with metrics enabled. Good: an enabled control reaches the same receiver through the same proxy. A control that sends straight to the Agent does not prove that the proxy forwards UDP.

Evidence:

• https://github.com/DataDog/system-tests/pull/8144#discussion_r4350952983
• https://github.com/DataDog/system-tests/pull/8080#discussion_r4342517264
• https://github.com/DataDog/system-tests/pull/6835
• https://github.com/DataDog/system-tests/pull/7129

ID: cursor-07

Title: Do not use private debug wording as the only proof.

Rule: Assert SDK behavior through its result, captured output, or a documented log contract. Do not use an undocumented debug message as the only proof that the behavior occurred.

Why: The SDK can change a private message without changing its behavior.

Detect: The assertion searches for a debug string that no documented contract defines.

Example: Bad: prove a span exists by finding `span created` in private debug logs. Good: inspect the captured span.

Evidence: https://github.com/DataDog/system-tests/pull/7516#discussion_r3812795148

ID: claude-13

Title: Read trace payloads through the protocol-agnostic helpers.

Rule: A test of behavior that does not depend on the trace encoding must give the same result for v0.4, v0.5, and v1.0 payloads. Compare trace IDs with `trace_id_equals()`, read the sampling priority with `get_sampling_priority()`, and filter intake requests with `interfaces.library.trace_paths`. Use `is_same_boolean()` only when the contract accepts `True`, `1`, and `"true"` as the same value. A test of the wire format itself must check the exact fields and types of its encoding.

Why: v1.0 encodes trace IDs as 128-bit hex strings, booleans as typed values, and missing span links as `[]`. A test written for one encoding fails or skips data when a tracer sends another.

Detect: A test that is not about the encoding compares raw fields, as in `span["trace_id"] == expected` or `meta[key] == "true"`. A test reads a sampling priority field directly. A path filter lists only `/v0.4/traces` or `/v0.5/traces`.

Example: Bad: `assert span["trace_id"] == int(expected_id)`. Good: `assert span.trace_id_equals(int(expected_id))`.

Evidence:

• https://github.com/DataDog/system-tests/pull/7449
• https://github.com/DataDog/system-tests/pull/7429
• https://github.com/DataDog/system-tests/pull/7419

ID: claude-16

Title: Keep library branches out of assertions, not out of setup.

Rule: Follow section 2 of https://github.com/DataDog/system-tests/blob/main/.cursor/rules/pr-review.mdc for assertion logic: a condition on the library must not change what a `test_*` method asserts. A `setup_*` method may use library-specific code when every branch triggers the same specified behavior.

Why: The assertion defines the shared contract, so it must be the same for every library. Triggering the behavior can need a different request per library, and flagging that setup code is a false positive.

Detect: Flag a condition on `context.library` that changes an assertion, in a `test_*` method or in a helper that only assertions use. Do not flag a read of `context.library` that leaves the assertion unchanged. Do not flag a `setup_*` branch that only changes which request triggers the behavior.

Example: Bad: `assert count == (2 if context.library == "java" else 1)`. Good: `setup_metrics` calls an exception endpoint only for .NET, so that the exception metric exists, and the test asserts the same values for every library.

Evidence:

• https://github.com/DataDog/system-tests/pull/7510#discussion_r3777433402

ID: codex-11

Title: Do not set the value the test expects.

Rule: Do not write the expected tag, code, or exporter result in the test app. The SDK must produce it. The assertion may name the value it expects. It must read that value from SDK output..

Why: If the test app writes the value, the assertion checks the test, not the SDK. A broken SDK, or a setting the SDK ignored, still passes.

Detect: The app adds `runtime-id` or another tag the SDK must produce. It copies SDK result codes into its own map. It forces an exporter that the configuration already selects.

Example: Bad: the app sets `runtime-id` on the span, and the test asserts that tag. Good: the tracer sets `runtime-id`, and the test asserts it on the captured span.

Evidence:

• https://github.com/DataDog/system-tests/pull/7496#discussion_r4094421958
• https://github.com/DataDog/system-tests/pull/7784
• https://github.com/DataDog/system-tests/pull/8001#discussion_r4231934847

ID: codex-21

Title: Check mocks against the real service contract.

Rule: When the test uses a fake Agent or backend, its request and response must match the real service. Check that shape in the spec, the real code, or a real capture. Do not copy the expected JSON from the fake. A deliberately broken response belongs only in the test of that error.

Why: The fake and its self-test can agree with each other and still be wrong. The real service then rejects what the fake sends.

Detect: The self-test imports every expected value from the fake. The fake returns a bare body where the real service uses an envelope. The fake sends config for a product the client did not ask for.

Example: Bad: a test returned the flag config as the whole body, and the self-test expected that same body. The real backend puts it under `data.attributes`. Good: test returns that envelope, and the check comes from the real contract.

Evidence:

• https://github.com/DataDog/system-tests/pull/7277
• https://github.com/DataDog/system-tests/pull/7315
• https://github.com/DataDog/system-tests/pull/7194
• https://github.com/DataDog/system-tests/pull/7175
