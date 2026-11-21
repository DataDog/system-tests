# Offline provider fixture

`core-provider-rules-wire.json` is a harness-specific derivative of the existing
`rules-wire.json`, originally from `openfeature-js-client/packages/browser/test/data/rules-v1-wire.json`.
The portable wire was generated with the rules codec at
[`d50b38c2`](https://github.com/DataDog/openfeature-js-client/commit/d50b38c2e4040946af79ec3d19f6483589a7ce13).
No credentials or customer configuration are included.

The decoded configuration has these deterministic rules:

| Flag | Condition | Value | Variant | Reason |
|--|--|--|--|--|
| `prerequisite` | `country` is `US` | `true` | `on` | `TARGETING_MATCH` |
| `prerequisite` | otherwise | `false` | `off` | `SPLIT` |
| `test-flag` | `prerequisite` has variant `on` | `true` | `on` | `TARGETING_MATCH` |
| `test-flag` | `prerequisite` has variant `off` | `false` | `off` | `SPLIT` |

Relative to `rules-wire.json`: add a boolean `off=false` variation and select it
in the fallback allocation; enable exposure logging for that allocation; clone
the flag as `prerequisite`; and give `test-flag`'s two allocations
`flagEvaluationStringMembership` conditions on `prerequisite`'s `on`/`off` variants.
Both flags use the original full 100-shard range, serial ID 7, and allocation keys.
The original fixture remains unchanged and is also used by the shared HTTP mock:
its fallback is `on=true`, so a successful server-channel refresh changes the value.

Expected values and subjects are asserted in Python, not computed by the adapter.
The adapter only deserializes the wire and uses the built package's public entry point.
