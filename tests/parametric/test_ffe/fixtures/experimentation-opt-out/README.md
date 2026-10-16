# Experimentation opt-out contract, version 1

This suite defines subject experimentation opt-out across providers, evaluators,
the Precompute API, and precompute clients. It includes **reviewed contract
inputs** and separately identified **compiler-generated artifacts**. Neither
fixture validation nor compiler generation proves that an SDK implements opt-out.

The contract uses the proposed winner-logging change: ordinary winner rollouts
have doLog=false. Active experiments, generated holdouts, and experiment-backed
canaries and bandits have doLog=true. The compiler must preserve ordinary
fallbacks when an experimental allocation can be skipped.

## Customer contract

The customer enables enableExperimentationOptOutParameter once on the provider
or native client. The customer supplies dd_experimentation_opt_out in the context.

| Provider activation | Attribute | Effective opt-out |
| --- | --- | --- |
| Absent or false | Any value | False |
| True | Boolean true | True |
| True | Missing, false, null, string, number, array, or object | False |

Read the typed boolean before converting context attributes to strings.
Do not coerce the string "true" or the number 1. Do not change the targeting key.

When effective opt-out is true, skip each allocation with doLog=true before
enrollment or arm selection. Continue ordinary allocations in their original
order. Do not force experimental control, false, or the application default.

Exclusion covers both experimental control and treatment. It also covers both
holdout groups and experiments that enroll 100% of subjects. Ordinary targeting,
percentage rollouts, and completed winners remain available.

Keep salts, shards, and weights unchanged. The eligible population retains
configured probabilities, not exact finite-population headcounts. Customers
must not derive eligibility from treatment assignment or treatment effects.

## Contents and exact coverage

The manifest lists every configuration, case ID, and sequence. Consumers must
read it. Unlisted files, missing cases, duplicate IDs, and wrong counts fail validation.

| Artifact | Purpose |
| --- | --- |
| configurations/supported.json | Ordinary rules, experiments, fallbacks, winner states, and holdout states. |
| configurations/legacy-without-capability.json | Old winner logging and a pruned fallback. Exclusion cannot safely use this artifact. |
| configurations/missing-dolog.json | Deliberately malformed marked JSON. Exclusion cannot treat a missing classification as ordinary. |
| configurations/compiler-*.json | Seven verbatim lifecycle outputs from the actual compiler with the proposed changes. |
| cases/activation.json | Explicit activation and strict boolean handling. |
| cases/evaluation.json | Allocation order, every randomized arm, identity, ordinary rollouts, winners, canaries, and bandits. |
| cases/holdouts.json | Both groups before shipment, after a non-control winner, and after a control winner. |
| cases/compatibility.json | Old or malformed configurations do not silently admit excluded subjects. |
| cases/telemetry.json | All four combinations of experimentation and evaluation-telemetry opt-out. |
| cases/compiler-generated.json | Thirty independently authored evaluations against generated lifecycle outputs. |
| compiler-generated/ | Paired protobuf bytes, generation provenance, observations, and independent shard vectors. |
| protocol/request-and-response.json | Actual request and response envelopes, malformed options, and missing acknowledgements. |
| sequences/ | Late responses, failed refresh, deduplication, logout, and cache identity. |

There are 136 evaluation cases, 20 protocol cases, and 9 client sequences.
The manifest defines 32 reviewed-input eligible-parity cases, 15 generated-input
eligible-parity cases, and a concurrent-server
check. Those checks reuse existing case IDs; they do not add new cases.

### Configuration provenance

The original three configurations specify expected behavior. Their provenance
is reviewed-contract-input. They must not be described as compiler-generated.

Seven additional configurations have compiler-generated provenance. The manifest
pairs each JSON file with its deterministic protobuf bytes and checks SHA256 for
both. It also checks the generation record and exact artifact enumeration.

The generation receipt is in compiler-generated/PROVENANCE.md. It records fixed
inputs, the command, exact source commit, generator hash, and successful invocation.
Generation ran from that clean commit. All generated artifacts match its output
byte for byte.

The generated scenarios cover active 50/50, active 100% single-arm, both completed
winners, and active/completed experiments combined with holdouts. Their JSON and
protobuf files were copied verbatim. Do not edit them to satisfy a consumer test;
regenerate them with the actual compiler and update the recorded provenance.

The generator's eligible examples in compiler-scenarios.json are observations
from its Go evaluator. They are **not** the shared expected-result oracle.
The thirty shared cases use different subject IDs and explicit expected identities.
Independent MD5 vectors establish holdout membership, group, and experimental arm.
The validator checks the vectors, not an alternate targeting evaluator.

The validator verifies protobuf bytes and pairing, but does not decode protobuf.
Consumers with protobuf support must decode the paired file and run the same
generated-input evaluation cases. Other adapters run the paired JSON.

Compiler tests must construct real lifecycle models and run the actual compiler.
Compare the relevant output with this contract. Establish these properties:

- Winner selection preserves the experiment link but clears winner doLog.
- Both generated holdout groups retain logging and analysis metadata.
- A non-control winner changes holdout exposure contexts as specified upstream.
- A control winner does not incorrectly start primary holdout analysis.
- Full-population experiments retain ordinary fallbacks and required variants.
- JSON, protobuf, and archived representations preserve the selected semantics.

UFC does not contain the retained experiment link. Fixtures cannot prove that
the database or compiler preserved it. Compiler lifecycle tests must supply
source provenance and a generator revision.

Canary and bandit cases cover their allocation classification after compilation.
They do not model bandit learning, action selection, or canary monitoring.

## Evaluation case format

Each case supplies providerOptions, typed context, an evaluation, and explicit
expected results. The expected.assignment identifies the allocation and split.
Never infer identity from value equality.

The expected.outcome is a test-harness category, **not a new SDK error code**:

| Outcome | Required behavior |
| --- | --- |
| assignment | Return the selected assignment and its exact identity. |
| no-assignment | Preserve the existing no-assignment result; the provider returns the caller default. |
| incompatible-configuration | Do not apply opt-out to old compiler semantics. Use the existing error/default path. |
| invalid-configuration | Do not classify malformed allocations as ordinary. Use the existing error/default path. |

Fixtures distinguish experimental control, ordinary fallback, and caller default.
One case gives control and fallback equal values but different allocation identities.
A boolean case requires an ordinary true, so forcing false cannot pass.

The wireReason is the selected split's reason in UFC or the precomputed payload.
Compiler and wire decoders must preserve it. Existing evaluator APIs can expose
different reason mappings. Compare each adapter's observable reason with its
unchanged eligible baseline. Do not invent an OPTED_OUT reason or silently
normalize existing reason behavior.

### Holdout identity

Route and search flags share the holdout key and cohort hash. They have distinct
generated allocation keys and serial IDs. Before shipment, both groups can
return the same value. Their group features and serial IDs still differ.

After a non-control winner ships, eligible subjects retain holdout assignments.
Excluded subjects skip the holdout and receive the ordinary winner. The
primary-analysis marker remains false for a control winner.

Assert assignment identity, serial ID, and the complete feature list.
Do not use holdout.should_include_in_holdout_analysis to decide eligibility.

## Compatibility and Precompute

Supported configurations declare:

    "evaluationCapabilities": ["experimentation-opt-out-v1"]

This marker attests to compiler winner classification, fallback preservation,
and holdout semantics. It is not an SDK version declaration.

With opt-out requested, a missing marker cannot produce a successful excluded
assignment. Ordinary requests retain existing behavior. Marked JSON also requires
explicit boolean doLog values for the evaluated flag's allocations. For protobuf,
the marker attests to compiler semantics; scalar presence is not required.
Archives must preserve the marker.

Ordinary missing-doLog behavior is not a universal assignment case. Current
Go and Rust JSON evaluators default it to true. Java and JavaScript default it
to false. Each adapter must run an ordinary missing-doLog regression against
its unchanged baseline and preserve that assignment and logging behavior.
Do not normalize these defaults as part of opt-out. The shared
missing-dolog-excluded case requires rejection when exclusion is requested.

The SDK sends the effective decision separately from targeting attributes:

    data.attributes.evaluation_options.experimentation_opt_out = true

False requests omit evaluation_options. The edge also accepts an explicit
boolean false or an empty options object. A targeting attribute alone cannot
activate exclusion. Non-boolean wire values are rejected.

A successful excluded response contains the same path with boolean true.
It means the evaluator applied exclusion using compatible configuration, not an
unconditional echo. Old edge code can ignore unknown fields, so HTTP success
alone does not prove support.

An excluded client rejects missing, false, malformed, or contradictory
acknowledgements. Ordinary clients accept legacy responses without this field.
A present acknowledgement must agree with the requested option.

Protocol cases test decoding and acceptance. Their fixed bodies do not prove
that the edge evaluated their corresponding request.

The option does not change the shared UFC cache key. Assignment caches and
request generations include subject, targeting context, environment, and
effective opt-out. A mismatch cannot publish or restore an old assignment.

## Telemetry and exposures

Cases reuse the existing precomputed EvaluationContext and Expectations schema
definitions and their ordered event matchers. Each case starts with clean state
and performs one evaluation:

- A selected doLog=true assignment produces one exposure.
- A skipped allocation produces no exposure and no deduplication entry.
- Evaluation telemetry stays enabled unless its independent control applies.
- Evaluation-telemetry opt-out does **not** suppress exposures or change assignment.
- noUnmatchedEvents=true requires exact observation, with a positive emission control.

Core evaluators return exposure eligibility; they do not necessarily emit events.
Core tests assert classification and identity. Runtime tests inspect actual
exposure events, evaluation events, and supported trace, metric, or RUM
annotations. A silent collector is not proof of suppression.

## Consumer responsibilities

| Consumer | Required checks |
| --- | --- |
| Compiler | Real lifecycle generation, compatibility, wire fields, preserved fallback variants, and format parity. |
| Core evaluator | Every evaluation case's effective option, outcome, identity, value, logging, serial ID, and features. |
| Provider | Strict activation through the public API; never inject the expected effective option into the provider. |
| Edge | Request parsing, both evaluator paths, acknowledgement correctness, and buffered/streamed output parity. |
| Precompute SDK | Public activation, outgoing options, response acceptance, typed getters, events, and all state sequences. |
| Server provider | Concurrent subject isolation on one provider using manifest case IDs and repetition count. |

Core adapters can calculate the effective option from fixture inputs because
activation is outside the core. Report that limited scope. A core pass is not
a provider activation pass.

Precompute adapters can encode the explicitly expected assignment as a mock
response. This is a mechanical field mapping, not another evaluator. Separately,
run the real edge against the same configuration and case. Compare its response
with the expected assignment.

Run every case in manifest.invariants.eligibleParityCaseIds and
manifest.compilerGeneration.eligibleParityCaseIds with activation enabled and disabled.
Use the same configuration and context. Require identical identity, value, serial ID,
features, exposure eligibility, and existing reason. The fixed MD5 vectors make
known arm selection independently inspectable. MD5 is the existing bucketing
contract, not a security mechanism.

For concurrent server cases, share one provider and run both contexts concurrently
for concurrentServerRepetitions iterations. Each result must match its own case.
Do not mutate global server context. Single-subject clients use transition sequences.

Test all supported representations. Backend Rust tests JSON and archived rkyv.
JavaScript tests JSON and protobuf. Report unsupported formats explicitly.

### Sequence actions

Start with empty assignments, cache, and exposure deduplication state. Use the
sequence flag and defaultValue. The default SDK environment is production;
configure and restart can specify another environment.

| Action | Test operation |
| --- | --- |
| configure | Initialize the real provider or native client with the specified options. |
| set-context | Change subject or attributes; assert immediately published state. |
| start-request | Start or observe refresh; keep its response pending and inspect outgoing options. |
| deliver-response | Encode the referenced assignment, set the requested acknowledgement, and deliver that pending response. |
| fail-request | Fail the pending request; assert which compatible state remains. |
| evaluate | Call the typed getter and inspect incremental exposure and evaluation-telemetry effects. |
| persist-cache | Wait for the real persistent write and retain its bytes under the test cache ID. |
| restart | Recreate the client with that saved cache and supplied identity. Inspect state before any new network response. |

An applied acknowledgement matches the pending request's effective option.
Missing removes the field. False supplies literal false. A null published case
means no assignment is available, not an assignment with a null value.

expectedExposureCount is incremental, not cumulative. Evaluation telemetry can
aggregate. Flush and compare logical evaluation counts with the existing platform adapter.

## Validation and reports

Install jsonschema, then run:

    python3 ci/validate-experimentation-opt-out.py
    python3 ci/test-validate-experimentation-opt-out.py

Validation checks schemas, duplicate JSON keys, exact manifest coverage,
references, strict activation, assignment consistency, metadata, protocol
expectations, and independent bucketing vectors. It does not evaluate targeting
rules or claim SDK conformance.

Consumer reports must include fixture Git SHA, compiler/evaluator revision,
manifest counts, executed IDs, failed IDs, unsupported IDs, representation, and
raw request/event receipts where relevant. Unsupported or skipped cases do not
count as passes. Keep runtime evidence separate from fixture validation.

Legacy suites remain unchanged. Old readers must not discover this directory
and silently ignore its provider, protocol, or sequence fields.
