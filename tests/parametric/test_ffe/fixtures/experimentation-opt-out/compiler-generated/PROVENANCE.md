# Compiler-generated experimentation opt-out fixtures

These files come from the production UFC compiler with fixed test inputs.
They are separate from the database lifecycle receipts, which use runtime identifiers and timestamps.

- Source repository: `ddoghq/dd-source`.
- Source commit: `654b5a5a34c9a74f223a8215b1202f47b9d3e0d8`.
- Generator: `domains/ffe/libs/flagging/ufc/experimentation_opt_out_test.go`, `TestCompilerExperimentationOptOutGeneratedFixtures`.
- Generator source SHA256: `4438ef0520626e75184690ffbcb0d37fcb55697b7ada220219befd51aeb2554d`.
- Successful invocation: `f1f65df6-3d14-4286-8d5a-6ce12973d504`.
- Fixed compilation time: `2026-10-16T12:00:00Z`.

Standalone generation command:

```sh
bzl test //domains/ffe/libs/flagging/ufc:go_default_test --test_filter=TestCompilerExperimentationOptOutGeneratedFixtures --test_output=errors
```

The recorded invocation ran from the clean source commit and passed in 4.090 seconds.
All seven JSON/protobuf pairs and compiler-scenarios.json match the checked-in artifacts byte for byte.

## Fixed inputs

| Input | Value |
| --- | --- |
| Organization | `123` |
| Flag ID / key / type | `opt-out-flag` / `planner` / string |
| Environment ID / name | `opt-out-env` / `experimentation-opt-out` |
| Allocation ID / key | `experiment-allocation` / `experiment` |
| Retained experiment ID | `experiment` |
| Variants | `control=experimental-control`, `treatment=experimental-treatment`, `baseline=ordinary-baseline` |
| Active two-arm weights | `50/50` |
| Active single-arm weights | `0/100`; experiment remains active |
| Completed weights | `100/0` or `0/100`; `ExperimentRolloutComplete=true` |
| Ordinary default | `baseline` |
| Standard serials | `101=control`, `102=treatment`, `900=default` |
| Holdout | `quarterly`, traffic `0.2`, status quo `control` |
| Holdout inclusion | `2026-10-16T09:00:00Z` through `2026-10-16T10:00:00Z` |
| Holdout analysis | `2026-10-16T11:00:00Z` through `2026-10-17T12:00:00Z` |
| Holdout contexts | `pre-ship`, `post-ship` |
| Holdout serials | pre: `201/202`; post: `301/302`, status-quo/all-shipped order |

The generator uses the existing compiler shard sizes and salts. It does not change them.
The control winner does not represent a shipped change. Its holdout keeps pre-ship serials and a false analysis flag.
The treatment winner uses post-ship holdout serials and a true analysis flag.

`compiler-scenarios.json` records the intended ordinary fallback and illustrative eligible assignment identities.
Its eligible examples come from the existing Go evaluator. Shared fixture checks must independently verify the hash vectors.
The generator does not claim that the new opt-out evaluator is implemented. That work belongs to stage 3.

The separate lifecycle integration test starts and concludes an experiment, then reloads through `GetFlagsWithRelations`.
It proves that production loads the completion state without injecting it into the compiler.
