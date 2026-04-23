# FFE Evaluation Reason — UFC Flag Examples

Reference companion to `reasons-and-errors-rfc.md` Appendix B.

Each section shows the full UFC payload required to trigger that reason/error combination.
Sections where no flag config is needed are marked accordingly.

For all examples:
- Flag key: replace with actual key under test
- `variationType` / `variations`: use type appropriate for the test evaluation call
- Caller attributes and `targetingKey` are noted in comments

---

## UFC envelope

All flag examples below are the value of the flag key inside `"flags"`.
Full envelope:

```json
{
  "createdAt": "2024-04-17T19:40:53.716Z",
  "format": "SERVER",
  "environment": {"name": "Test"},
  "flags": {
    "my-flag": { "<flag definition below>" }
  }
}
```

---

## REASON-1 — ERROR / PROVIDER_NOT_READY

**No flag config needed.**

Provider has not yet received any valid configuration. Evaluation occurs before the first successful config fetch.

```
No UFC payload — evaluate any flag key before config is loaded.
```

---

## REASON-2 — ERROR / PROVIDER_FATAL

**No flag config needed.**

Provider received a non-retryable 4XX (400, 401, 403, 404) from the assignments endpoint.
All evaluations return the coded default regardless of what flags exist.

```
No UFC payload — trigger via a 4XX response from the assignments/config endpoint.
```

---

## REASON-3 — ERROR / FLAG_NOT_FOUND

**Requested key is absent from the config.**

A different flag is present (config is loaded), but the evaluated key does not exist.
Disabled flags are also absent from the precomputed dataset — operationally identical.

```json
{
  "key": "some-other-flag",
  "enabled": true,
  "variationType": "STRING",
  "variations": {
    "on": {"key": "on", "value": "on-value"},
    "off": {"key": "off", "value": "off-value"}
  },
  "allocations": [
    {
      "key": "default-allocation",
      "rules": [],
      "splits": [{"variationKey": "on", "shards": []}],
      "doLog": true
    }
  ]
}
```

```
Evaluate: "my-flag"  (key not present in config)
Result:   coded default / ERROR / FLAG_NOT_FOUND
```

---

## REASON-4 — ERROR / TYPE_MISMATCH

Flag is configured as `STRING`. Caller requests a `BOOLEAN` evaluation.
Type conversion fails after core evaluation returns.

```json
{
  "key": "my-flag",
  "enabled": true,
  "variationType": "STRING",
  "variations": {
    "on": {"key": "on", "value": "on-value"},
    "off": {"key": "off", "value": "off-value"}
  },
  "allocations": [
    {
      "key": "default-allocation",
      "rules": [],
      "splits": [{"variationKey": "on", "shards": []}],
      "doLog": true
    }
  ]
}
```

```
Evaluate: getBooleanValue("my-flag", false)
Result:   coded default / ERROR / TYPE_MISMATCH
```

---

## REASON-5 — ERROR / PARSE_ERROR

**No flag config achievable via RC mock.**

Entire config payload must be unparseable (raw non-JSON body).
Per-flag parse failures do not produce this code — SDKs omit the bad flag and return FLAG_NOT_FOUND.
Requires raw body injection below the RC mock layer.

```
No UFC payload — requires fault injection (raw non-JSON response body).
Not testable via RC mock framework.
```

---

## REASON-6 — ERROR / GENERAL

**No reproducible flag structure.**

Catch-all for unclassified internal SDK errors.
No flag shape reliably triggers this via the weblog/RC interface.

```
No UFC payload — requires SDK internals access or fault injection
below the surface accessible to system tests.
```

---

## REASON-7 — ERROR / TARGETING_KEY_MISSING

Allocation has a non-trivial shard (real hash ranges).
Evaluation path reaches shard computation.
No targeting key is provided → hash cannot be computed → error.

```json
{
  "key": "my-flag",
  "enabled": true,
  "variationType": "STRING",
  "variations": {
    "on": {"key": "on", "value": "on-value"},
    "off": {"key": "off", "value": "off-value"}
  },
  "allocations": [
    {
      "key": "shard-alloc",
      "rules": [],
      "splits": [
        {
          "variationKey": "on",
          "shards": [
            {
              "salt": "rfc-salt",
              "totalShards": 10000,
              "ranges": [{"start": 0, "end": 10000}]
            }
          ]
        }
      ],
      "doLog": true
    }
  ]
}
```

```
targetingKey: ""   (empty / absent)
attributes:   {}
Result:       coded default / ERROR / TARGETING_KEY_MISSING
```

---

## REASON-8 — TARGETING_MATCH (rule-only, no shard, no key required)

Allocation has a targeting rule and a vacuous split (`shards: []`).
Vacuous split skips hash computation entirely → no targeting key required.
Rule matches via subject attribute.

```json
{
  "key": "my-flag",
  "enabled": true,
  "variationType": "STRING",
  "variations": {
    "on": {"key": "on", "value": "on-value"},
    "off": {"key": "off", "value": "off-value"}
  },
  "allocations": [
    {
      "key": "rule-alloc",
      "rules": [
        {
          "conditions": [
            {
              "operator": "ONE_OF",
              "attribute": "tier",
              "value": ["gold"]
            }
          ]
        }
      ],
      "splits": [{"variationKey": "on", "shards": []}],
      "doLog": true
    }
  ]
}
```

```
targetingKey: ""              (empty — no key needed)
attributes:   {tier: "gold"}  (matches rule)
Result:       platform value / TARGETING_MATCH / variant=on / allocationKey=rule-alloc
```

---

## REASON-9 — DEFAULT (coded default, zero allocations)

Flag exists in config but has an empty allocations waterfall.
No evaluation possible — ADR-001 data-invariant case.

```json
{
  "key": "my-flag",
  "enabled": true,
  "variationType": "STRING",
  "variations": {
    "on": {"key": "on", "value": "on-value"},
    "off": {"key": "off", "value": "off-value"}
  },
  "allocations": []
}
```

```
targetingKey: "user-1"
attributes:   {}
Result:       coded default / DEFAULT / no error code
              variant tag: absent or "n/a"
```

---

## REASON-10 — DEFAULT (coded default, no default alloc, no match)

Non-empty waterfall. Rule-based allocation present but subject doesn't match.
No default (unconditional) allocation at the end of the waterfall.
ADR-001 data-invariant case: coded default, DEFAULT, no error.

```json
{
  "key": "my-flag",
  "enabled": true,
  "variationType": "STRING",
  "variations": {
    "on": {"key": "on", "value": "on-value"},
    "off": {"key": "off", "value": "off-value"}
  },
  "allocations": [
    {
      "key": "rule-only-alloc",
      "rules": [
        {
          "conditions": [
            {
              "operator": "ONE_OF",
              "attribute": "tier",
              "value": ["platinum"]
            }
          ]
        }
      ],
      "splits": [{"variationKey": "on", "shards": []}],
      "doLog": true
    }
  ]
}
```

```
targetingKey: "user-1"
attributes:   {tier: "bronze"}  (does not match "platinum")
Result:       coded default / DEFAULT / no error code
              variant tag: absent or "n/a"
```

---

## REASON-11 — DEFAULT (no split entry → allocation skipped → waterfall exhausted)

Single allocation. No targeting rules. No date window.
**No split entries** (`splits: []` — empty array, not a split entry with empty shards).

An allocation with `splits: []` cannot produce a variant — there is no split entry to resolve a
variation key. The allocation is skipped even though rules pass. With no subsequent allocation, the
waterfall is exhausted → coded default / DEFAULT / no error code.

> **REASON-11 vs REASON-12:** The structural difference is whether a split *entry* exists at all.
> - REASON-11: `splits: []` — no split entries; allocation cannot resolve a variant; allocation skipped → DEFAULT (coded default)
> - REASON-12: `splits: [{"variationKey": "on", "shards": []}]` — one entry with empty `shards`; resolves vacuously → STATIC (platform value)
>
> These produce **different results**. REASON-11 exhausts the waterfall without selecting a variant.
> REASON-12 selects the variation from the split entry without hashing.

```json
{
  "key": "my-flag",
  "enabled": true,
  "variationType": "STRING",
  "variations": {
    "on": {"key": "on", "value": "on-value"},
    "off": {"key": "off", "value": "off-value"}
  },
  "allocations": [
    {
      "key": "static-alloc",
      "rules": [],
      "splits": [],
      "doLog": true
    }
  ]
}
```

```
targetingKey: "user-1"
attributes:   {}
Result:       coded default / DEFAULT / no error code
              variant tag: absent or "n/a"  (allocation skipped; no variation resolved)
```

---

## REASON-12 — STATIC (vacuous split, shards:[])

Single allocation. No targeting rules. No date window.
Split entry exists but `shards` is an empty array — matches vacuously, no MD5 hash computed.

```json
{
  "key": "my-flag",
  "enabled": true,
  "variationType": "STRING",
  "variations": {
    "on": {"key": "on", "value": "on-value"},
    "off": {"key": "off", "value": "off-value"}
  },
  "allocations": [
    {
      "key": "default-allocation",
      "rules": [],
      "splits": [{"variationKey": "on", "shards": []}],
      "doLog": true
    }
  ]
}
```

```
targetingKey: "user-1"
attributes:   {}
Result:       platform value / STATIC / allocationKey=default-allocation
```

---

## REASON-13 — TARGETING_MATCH (multi-alloc, rule matches, no split)

Multi-allocation waterfall. First allocation has a targeting rule; vacuous split.
Subject attributes match the rule → TARGETING_MATCH. Default allocation is unreached.

```json
{
  "key": "my-flag",
  "enabled": true,
  "variationType": "STRING",
  "variations": {
    "on": {"key": "on", "value": "on-value"},
    "off": {"key": "off", "value": "off-value"}
  },
  "allocations": [
    {
      "key": "rule-alloc",
      "rules": [
        {
          "conditions": [
            {
              "operator": "ONE_OF",
              "attribute": "plan",
              "value": ["enterprise"]
            }
          ]
        }
      ],
      "splits": [{"variationKey": "on", "shards": []}],
      "doLog": true
    },
    {
      "key": "default-alloc",
      "rules": [],
      "splits": [{"variationKey": "off", "shards": []}],
      "doLog": true
    }
  ]
}
```

```
targetingKey: "user-1"
attributes:   {plan: "enterprise"}  (matches rule)
Result:       platform value / TARGETING_MATCH / variant=on / allocationKey=rule-alloc
```

---

## REASON-14 — DEFAULT (multi-alloc, rule fails, default catches)

Same flag as REASON-13. Subject attributes do not match the rule.
Rule-based allocation skipped. Default allocation catches → platform value.

```json
// Same flag definition as REASON-13
```

```
targetingKey: "user-1"
attributes:   {plan: "starter"}    (does not match "enterprise")
Result:       platform value / DEFAULT / variant=off / allocationKey=default-alloc
```

---

## REASON-15 — SPLIT (non-vacuous split, subject bucketed)

Single allocation. No targeting rules. Real shard ranges with 50/50 split.
Subject is placed in a shard via hash computation → SPLIT.

```json
{
  "key": "my-flag",
  "enabled": true,
  "variationType": "STRING",
  "variations": {
    "on": {"key": "on", "value": "on-value"},
    "off": {"key": "off", "value": "off-value"}
  },
  "allocations": [
    {
      "key": "split-allocation",
      "rules": [],
      "splits": [
        {
          "variationKey": "on",
          "shards": [
            {
              "salt": "test-salt",
              "totalShards": 10000,
              "ranges": [{"start": 0, "end": 5000}]
            }
          ]
        },
        {
          "variationKey": "off",
          "shards": [
            {
              "salt": "test-salt",
              "totalShards": 10000,
              "ranges": [{"start": 5000, "end": 10000}]
            }
          ]
        }
      ],
      "doLog": true
    }
  ]
}
```

```
targetingKey: "user-1"   (hash determines bucket)
attributes:   {}
Result:       platform value / SPLIT / variant determined by hash
```

---

## REASON-16 — DEFAULT (rule passes, shard guaranteed miss, default catches)

Allocation has both a targeting rule and a 0% shard (`ranges: []`).
Rule passes. Shard has empty ranges → guaranteed miss. Allocation is skipped.
Default allocation catches.

```json
{
  "key": "my-flag",
  "enabled": true,
  "variationType": "STRING",
  "variations": {
    "on": {"key": "on", "value": "on-value"},
    "off": {"key": "off", "value": "off-value"}
  },
  "allocations": [
    {
      "key": "rule-shard-alloc",
      "rules": [
        {
          "conditions": [
            {
              "operator": "ONE_OF",
              "attribute": "group",
              "value": ["beta"]
            }
          ]
        }
      ],
      "splits": [
        {
          "variationKey": "on",
          "shards": [
            {
              "salt": "rfc-salt",
              "totalShards": 10000,
              "ranges": []
            }
          ]
        }
      ],
      "doLog": true
    },
    {
      "key": "default-alloc",
      "rules": [],
      "splits": [{"variationKey": "off", "shards": []}],
      "doLog": true
    }
  ]
}
```

```
targetingKey: "user-1"
attributes:   {group: "beta"}   (rule passes; 0% shard guarantees miss)
Result:       platform value / DEFAULT / variant=off / allocationKey=default-alloc
```

---

## REASON-17 — SPLIT (rule passes AND shard guaranteed hit)

Same structure as REASON-16 but shard is 100% (`ranges: [{start:0, end:10000}]`).
Rule passes and shard always hits. Per ADR-004, SPLIT takes precedence over TARGETING_MATCH when
a non-trivial shard resolves the subject — regardless of whether targeting rules were also present.

```json
{
  "key": "my-flag",
  "enabled": true,
  "variationType": "STRING",
  "variations": {
    "on": {"key": "on", "value": "on-value"},
    "off": {"key": "off", "value": "off-value"}
  },
  "allocations": [
    {
      "key": "rule-shard-alloc",
      "rules": [
        {
          "conditions": [
            {
              "operator": "ONE_OF",
              "attribute": "group",
              "value": ["alpha"]
            }
          ]
        }
      ],
      "splits": [
        {
          "variationKey": "on",
          "shards": [
            {
              "salt": "rfc-salt",
              "totalShards": 10000,
              "ranges": [{"start": 0, "end": 10000}]
            }
          ]
        }
      ],
      "doLog": true
    },
    {
      "key": "default-alloc",
      "rules": [],
      "splits": [{"variationKey": "off", "shards": []}],
      "doLog": true
    }
  ]
}
```

```
targetingKey: "user-1"
attributes:   {group: "alpha"}   (rule passes; 100% shard always hits)
Result:       platform value / SPLIT / variant=on   (ADR-004: SPLIT takes precedence over TARGETING_MATCH)
```

---

## REASON-18 — DEFAULT (rule fails, default catches)

Same flag as REASON-17. Subject attributes do not match the rule.
Rule fails → allocation skipped entirely (shard is not reached). Default catches.

```json
// Same flag definition as REASON-17
```

```
targetingKey: "user-1"
attributes:   {group: "beta"}    (rule requires "alpha" → fails)
Result:       platform value / DEFAULT / variant=off / allocationKey=default-alloc
```

---

## REASON-19 — TARGETING_MATCH (split alloc skipped/miss, rule alloc 2 matches)

Three-allocation waterfall:
1. Split-only alloc with 0% shard → guaranteed miss → skipped
2. Rule-based alloc → rule matches → TARGETING_MATCH
3. Default alloc → unreached

```json
{
  "key": "my-flag",
  "enabled": true,
  "variationType": "STRING",
  "variations": {
    "on": {"key": "on", "value": "on-value"},
    "off": {"key": "off", "value": "off-value"}
  },
  "allocations": [
    {
      "key": "split-alloc",
      "rules": [],
      "splits": [
        {
          "variationKey": "on",
          "shards": [
            {
              "salt": "rfc-salt",
              "totalShards": 10000,
              "ranges": []
            }
          ]
        }
      ],
      "doLog": true
    },
    {
      "key": "rule-alloc",
      "rules": [
        {
          "conditions": [
            {
              "operator": "ONE_OF",
              "attribute": "region",
              "value": ["us-east"]
            }
          ]
        }
      ],
      "splits": [{"variationKey": "on", "shards": []}],
      "doLog": true
    },
    {
      "key": "default-alloc",
      "rules": [],
      "splits": [{"variationKey": "off", "shards": []}],
      "doLog": true
    }
  ]
}
```

```
targetingKey: "user-1"
attributes:   {region: "us-east"}   (split-alloc: 0% miss; rule-alloc: matches)
Result:       platform value / TARGETING_MATCH / variant=on / allocationKey=rule-alloc
```

---

## REASON-20 — DEFAULT (split alloc skipped/miss, default catches)

Same flag as REASON-19. Subject doesn't match the rule in alloc 2.
Split misses, rule fails, default catches.

```json
// Same flag definition as REASON-19
```

```
targetingKey: "user-1"
attributes:   {region: "eu-west"}   (split-alloc: 0% miss; rule-alloc: fails)
Result:       platform value / DEFAULT / variant=off / allocationKey=default-alloc
```

---

## REASON-21 — DEFAULT (single alloc, active date window, no rules, no split)

Single allocation. `startAt`/`endAt` present; window is currently active.
No targeting rules. Vacuous split.
Per ADR-003: presence of `startAt`/`endAt` precludes STATIC → DEFAULT.

```json
{
  "key": "my-flag",
  "enabled": true,
  "variationType": "STRING",
  "variations": {
    "on": {"key": "on", "value": "on-value"},
    "off": {"key": "off", "value": "off-value"}
  },
  "allocations": [
    {
      "key": "window-alloc",
      "startAt": "2020-01-01T00:00:00Z",
      "endAt": "2099-01-01T00:00:00Z",
      "rules": [],
      "splits": [{"variationKey": "on", "shards": []}],
      "doLog": true
    }
  ]
}
```

```
targetingKey: "user-1"
attributes:   {}
Result:       platform value / DEFAULT / variant=on
              (not STATIC — date window present per ADR-003)
```

---

## REASON-22 — DEFAULT (coded default, single alloc, inactive window)

Single allocation. Window has expired. No active allocation matches.
No default allocation present. ADR-001 data-invariant case → coded default, DEFAULT, no error.
Flag IS present in config — expired window is not FLAG_NOT_FOUND.

```json
{
  "key": "my-flag",
  "enabled": true,
  "variationType": "STRING",
  "variations": {
    "on": {"key": "on", "value": "on-value"},
    "off": {"key": "off", "value": "off-value"}
  },
  "allocations": [
    {
      "key": "window-alloc",
      "startAt": "2020-01-01T00:00:00Z",
      "endAt": "2020-12-31T00:00:00Z",
      "rules": [],
      "splits": [{"variationKey": "on", "shards": []}],
      "doLog": true
    }
  ]
}
```

```
targetingKey: "user-1"
attributes:   {}
Result:       coded default / DEFAULT / no error code
              variant tag: absent or "n/a"  (no allocation matched)
```

---

## REASON-23 — DEFAULT (multi-alloc, first alloc active window, no rules/split)

First allocation has an active date window, no rules, vacuous split.
Window fires. Per ADR-003: date window precludes STATIC → DEFAULT.
Second allocation (default) is unreached.

```json
{
  "key": "my-flag",
  "enabled": true,
  "variationType": "STRING",
  "variations": {
    "on": {"key": "on", "value": "on-value"},
    "off": {"key": "off", "value": "off-value"}
  },
  "allocations": [
    {
      "key": "window-alloc",
      "startAt": "2020-01-01T00:00:00Z",
      "endAt": "2099-01-01T00:00:00Z",
      "rules": [],
      "splits": [{"variationKey": "on", "shards": []}],
      "doLog": true
    },
    {
      "key": "default-alloc",
      "rules": [],
      "splits": [{"variationKey": "off", "shards": []}],
      "doLog": true
    }
  ]
}
```

```
targetingKey: "user-1"
attributes:   {}
Result:       platform value / DEFAULT / variant=on
              (variant=on confirms window-alloc fired, not default-alloc)
```

---

## REASON-24 — DEFAULT (multi-alloc, first alloc window inactive, default catches)

First allocation window has expired → skipped.
Default allocation catches → platform value.

```json
{
  "key": "my-flag",
  "enabled": true,
  "variationType": "STRING",
  "variations": {
    "on": {"key": "on", "value": "on-value"},
    "off": {"key": "off", "value": "off-value"}
  },
  "allocations": [
    {
      "key": "window-alloc",
      "startAt": "2020-01-01T00:00:00Z",
      "endAt": "2020-12-31T00:00:00Z",
      "rules": [],
      "splits": [{"variationKey": "on", "shards": []}],
      "doLog": true
    },
    {
      "key": "default-alloc",
      "rules": [],
      "splits": [{"variationKey": "off", "shards": []}],
      "doLog": true
    }
  ]
}
```

```
targetingKey: "user-1"
attributes:   {}
Result:       platform value / DEFAULT / variant=off
              (variant=off distinguishes from REASON-23 where window-alloc fires)
```

---

## REASON-25 — TARGETING_MATCH (active window + rule matches, no split)

Allocation has both an active date window and targeting rules. Window is active.
Rule matches → TARGETING_MATCH.
Window alone does not imply TARGETING_MATCH; rules do.

```json
{
  "key": "my-flag",
  "enabled": true,
  "variationType": "STRING",
  "variations": {
    "on": {"key": "on", "value": "on-value"},
    "off": {"key": "off", "value": "off-value"}
  },
  "allocations": [
    {
      "key": "window-rule-alloc",
      "startAt": "2020-01-01T00:00:00Z",
      "endAt": "2099-01-01T00:00:00Z",
      "rules": [
        {
          "conditions": [
            {
              "operator": "ONE_OF",
              "attribute": "segment",
              "value": ["vip"]
            }
          ]
        }
      ],
      "splits": [{"variationKey": "on", "shards": []}],
      "doLog": true
    },
    {
      "key": "default-alloc",
      "rules": [],
      "splits": [{"variationKey": "off", "shards": []}],
      "doLog": true
    }
  ]
}
```

```
targetingKey: "user-1"
attributes:   {segment: "vip"}   (window active; rule matches)
Result:       platform value / TARGETING_MATCH / variant=on / allocationKey=window-rule-alloc
```

---

## REASON-26 — DEFAULT (active window + rule fails, default catches)

Same flag as REASON-25. Subject doesn't match the rule.
Window is active but rule fails → allocation skipped. Default catches.

```json
// Same flag definition as REASON-25
```

```
targetingKey: "user-1"
attributes:   {segment: "standard"}   (rule requires "vip" → fails)
Result:       platform value / DEFAULT / variant=off / allocationKey=default-alloc
```

---

## Summary

Return value key: **Platform** = variant from flag config; **Coded** = developer's fallback value (ADR-001: rows 9, 10, 22 return coded default with DEFAULT reason, not an error).

| # | Flag present | Return | Key shape | Reason | Error code |
|---|---|---|---|---|---|
| 1 | No | Coded | N/A — no config loaded | ERROR | PROVIDER_NOT_READY |
| 2 | No | Coded | N/A — 4XX response | ERROR | PROVIDER_FATAL |
| 3 | No (key absent) | Coded | Different key in config | ERROR | FLAG_NOT_FOUND |
| 4 | Yes | Coded | STRING flag, evaluated as BOOLEAN | ERROR | TYPE_MISMATCH |
| 5 | No | Coded | N/A — unparseable payload | ERROR | PARSE_ERROR |
| 6 | No | Coded | N/A — internal error | ERROR | GENERAL |
| 7 | Yes | Coded | Single alloc, real shard, no rules | ERROR | TARGETING_KEY_MISSING |
| 8 | Yes | Platform | Single alloc, rule, vacuous split | TARGETING_MATCH | — |
| 9 | Yes | **Coded** ¹ | `allocations: []` | DEFAULT | — |
| 10 | Yes | **Coded** ¹ | Rule alloc only, no default alloc | DEFAULT | — |
| 11 | Yes | **Coded** ¹ | Single alloc, `splits: []`, no rules, no window — alloc skipped, waterfall exhausted | DEFAULT | — |
| 12 | Yes | Platform | Single alloc, `splits: [{shards:[]}]`, no rules, no window | STATIC | — |
| 13 | Yes | Platform | Rule alloc + default alloc; rule matches | TARGETING_MATCH | — |
| 14 | Yes | Platform | Rule alloc + default alloc; rule fails | DEFAULT | — |
| 15 | Yes | Platform | Single alloc, real shard ranges, no rules | SPLIT | — |
| 16 | Yes | Platform | Rule + 0% shard alloc + default alloc; rule passes, shard misses | DEFAULT | — |
| 17 | Yes | Platform | Rule + 100% shard alloc + default alloc; rule + shard win | SPLIT | — |
| 18 | Yes | Platform | Rule + 100% shard alloc + default alloc; rule fails | DEFAULT | — |
| 19 | Yes | Platform | 0% shard alloc → rule alloc → default alloc; rule matches | TARGETING_MATCH | — |
| 20 | Yes | Platform | 0% shard alloc → rule alloc → default alloc; rule fails | DEFAULT | — |
| 21 | Yes | Platform | Single alloc, active window, no rules, vacuous split | DEFAULT | — |
| 22 | Yes | **Coded** ¹ | Single alloc, expired window | DEFAULT | — |
| 23 | Yes | Platform | Active-window alloc + default alloc; window fires | DEFAULT | — |
| 24 | Yes | Platform | Expired-window alloc + default alloc; default catches | DEFAULT | — |
| 25 | Yes | Platform | Active-window + rule alloc + default alloc; rule matches | TARGETING_MATCH | — |
| 26 | Yes | Platform | Active-window + rule alloc + default alloc; rule fails | DEFAULT | — |

¹ ADR-001 exception: coded default with DEFAULT reason and no error code. These are data-invariant violations (empty waterfall / no allocation matched / expired single window with no fallback), not SDK errors.
