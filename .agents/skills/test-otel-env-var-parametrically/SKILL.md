---
name: test-otel-env-var-parametrically
description: >-
  Add or refine parametric coverage for an OpenTelemetry OTEL_* environment
  variable, including value matrices, defaults, registry-based manifest
  declarations, and migration of existing variable-specific tests.
---

# Test an OTel environment variable parametrically

Build specification-based configuration coverage for one `OTEL_*` variable
in this repository.

## Organize the tests

Put all new OTel environment-variable coverage in:

```text
tests/parametric/otel_env_vars/
```

Use one file per variable, named after the lowercased variable, and one class
named after the variable. For example:

```text
tests/parametric/otel_env_vars/test_otel_sdk_disabled.py
Test_OTEL_SDK_DISABLED
```

Move existing tests that specifically exercise that variable into its file.
Preserve their assertions unless the requested contract supersedes them. Do
not move broader multi-variable, telemetry, or interoperability coverage.

## Establish the contract

1. Read the variable entry and its type-specific guidance in the official
   OpenTelemetry specification.
2. Inspect existing system tests and tracer mappings so the assertion uses the
   narrowest stable configuration surface available.
3. Query the current APM configuration registry by exact variable name at
   `https://dd-feature-parity.azurewebsites.net/configurations`. Inspect every
   current, non-deprecated variant and its language implementation ranges.

If registry variants disagree or appear stale, inspect tracer source before
choosing declarations and report the discrepancy to the user.

## Define the value matrices

- When the specification defines fewer than ten semantic values, test every
  value.
- For a large or infinite value domain, propose a small matrix to the user
  before implementing it. Usually choose two or three representative values
  when behavior is uniform, plus meaningful boundaries and specified invalid
  cases.
- Put stable values in one parameter matrix. Put deprecated values in a
  separate matrix so their support can be declared independently.
- Give every case a readable parameter ID based on the wire value or boundary.

## Assert configuration support

Prove that setting the environment variable changes the effective
configuration. Reading the process environment back is not evidence of
support.

Prefer `/trace/config`, configuration telemetry, or a published startup value,
in that order. Neutralize harness defaults and unrelated settings that can mask
the variable or cause unrelated signal exporters to start.

Test the default with no value supplied. The tests must establish both that it
is sensible and that it matches the OTel specification. Use one test when those
are the same fact; use separate, clearly named tests when they differ.

In most cases, do not test the complete runtime behavior controlled by the
setting. When that behavior is straightforward to observe, propose the extra
behavioral coverage to the user before adding it and keep it separate from the
configuration matrix.

## Declare language support

Update every tracer manifest for the new path.

- Enable a supported language from the registry's current implementation
  boundary.
- Explicitly disable every language absent from the registry with a bare
  `missing_feature` declaration. Registry absence selects the declaration but
  is not evidence for a reason, so do not mention it in the manifest.
- Use `missing_feature` when the configuration is not implemented,
  `irrelevant` only when the setting cannot apply to that tracer, and
  `incomplete_test_app` when support exists but the parametric application
  cannot expose the chosen configuration surface.
- Use `bug` when a registry-supported behavior has an unintuitive or
  undocumented gap. Do not classify an intentional, documented numeric
  default difference, such as a timeout, as a bug merely because it differs
  from the OTel specification. Ask the user when the classification is not
  clear, and always include the dedicated defect ticket required by a bug
  declaration. Do not reuse the test-implementation ticket as a bug ticket.
- Add narrower method declarations when a language supports only part of a
  matrix or fails the specification default.
- Keep declaration reasons concise: state only the behavior that explains the
  gap.

Do not infer support from an old test that passes accidentally because the
observed configuration already has the expected default.

## Prepare a pull request

Find the variable's ticket in
[the bundled ticket map](references/otel-environment-variable-sections.csv)
and reference it in the pull request. Do not guess the ticket from a nearby
variable.

After a pull request is opened, proactively offer to transition that ticket to
`Reviewable` / `In Review`. Do not transition it without the user's approval.

## Verify and stop

Format and lint the touched files, validate manifests, collect the new file,
and run it against at least one enabled language. Force-run narrower disabled
cases only when needed to confirm their declaration reason. Stop after the
configuration contract, migrated coverage, and manifest states are proven.
