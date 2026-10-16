# Experimentation opt-out runtime contract

This companion suite tests the real Java provider through its public evaluation API.
It checks values, allocation keys, variant keys, serial IDs, exposure classification, and hook metadata.
It does not infer success from an application default with an equal value.

## Shared inputs

The nested fixture snapshot comes from [shared fixture PR #48](https://github.com/DataDog/ffe-system-test-data/pull/48).
The exact commit is `5e2430d9ad36644e2cecb6a32ddb8d05d7c98ac6`.
`fixtures/experimentation-opt-out/SOURCE.json` records every original Git blob ID.
The loader verifies every blob and all 136 case IDs before using the snapshot.
Do not edit copied configurations or expectations. Update the shared repository and refresh the snapshot together.

The runtime suite executes 116 cases in 11 configuration/provider-option groups.
It excludes 20 cases with fixed allocation time boundaries.
The Java SDK fixture adapter covers those cases with its fixed-clock test seam.
The dogfooding companion also runs them while their original time window is valid.
Changing generated dates would invalidate that proof.

## Local candidate run

Copy the agent, provider, and API JARs from the same candidate build into `binaries/`.
Do not combine a released agent with a candidate provider.
The Java image installer already accepts all three local JARs.

```sh
PYTEST_XDIST_AUTO_NUM_WORKERS=1 TEST_LIBRARY=java ./run.sh PARAMETRIC \
  tests/parametric/test_ffe/test_experimentation_opt_out.py --runxfail
```

`run.sh` appends `-n auto`. The environment variable bounds that setting to one worker.
Use `--skip-parametric-build` only when the image and candidate artifacts did not change.
The manifest marks this unreleased behavior as `missing_feature` without inventing a release version.
The local command uses `--runxfail` so a candidate failure fails the run.
The suite enables the existing span-enrichment setting so ordinary allocation serial metadata is observable.
This does not enable experimentation opt-out. The public provider option controls that behavior separately.

`ffe_start(provider_options=...)` activates the public provider options before evaluation.
A missing option method is a setup failure, not a behavioral negative control.
The baseline negative control uses the existing evaluation path without the new method.
Contexts remain per evaluation. The test does not replace server-global subject state.

The Java controllers retain JSON integers that Jackson parses as `Long`.
They convert these values through OpenFeature's supported `Double` context type.
The bounded regression in `test_dynamic_evaluation.py` checks an exactly representable integer and both adjacent values.
This does not add exact 64-bit integer support to the SDK.

## Evidence boundary

These groups check assignment behavior only. The SDK shares exposure deduplication across providers.
Repeated fixture subjects can therefore suppress duplicate exposures correctly.
The dogfooding companion restarts its own app between the four independent telemetry cases.
It retains exact per-subject exposure and evaluation receipts, metrics, and correlated assignment traces.
It also checks overlapping evaluations and confirms that a skipped assignment does not reserve a deduplication key.

The 20 Precompute protocol cases and nine client state sequences do not apply to this server runtime suite.
