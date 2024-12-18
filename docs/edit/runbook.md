⚠️ Did this test just fail, and you want to fix it? ⚠️

Here's what you need to do!

## test_telemetry.py

### test_config_telemetry_completeness

#### Summary

This can be **easily fixed** in ~5 minutes

This is **caused by adding a new config option** without adding the associated config normalization rules to telemetry intake

The impact is that these **configs are not visible** in Metabase, REDAPL, or anywhere else

#### Runbook

1. Check the test failure to see exactly which configs are missing
2. Add config normalization rules [here](https://github.com/DataDog/dd-go/tree/prod/trace/apps/tracer-telemetry-intake/telemetry-payload/static/) following the existing pattern 
   1. This can be merged with any review from [@apm-ecosystems](https://github.com/orgs/DataDog/teams/apm-ecosystems)
3. After merging, update system-tests by running [update.sh](/tests/telemetry_intake/update.sh)
   1. This can be run from the root by running `./tests/telemetry_intake/update.sh`
   2. This can be merged with any review from [@apm-ecosystems](https://github.com/orgs/DataDog/teams/apm-ecosystems)
4. You're all set - your tests should pass 🏁

#### Details
The specific test that failed is:

```python
tests.test_telemetry.test_config_telemetry_completeness
```

This asserts that config telemetry is handled properly by telemetry intake

Some files are manually copied from dd-go from/to the following paths using tests/telemetry_intake/update.sh
from: https://github.com/DataDog/dd-go/blob/prod/trace/apps/tracer-telemetry-intake/telemetry-payload/static/
to: tests/telemetry_intake/static

If this test fails, it means that a telemetry key was found in config telemetry that does not
exist in any of the files listed above in dd-go
The impact is that telemetry will not be reported to the Datadog backend won't be unusable

To fix this, you must update dd-go to either
1) Add an exact config key to match config_norm_rules.json
2) Add a prefix that matches the config keys to config_prefix_block_list.json
3) Add a prefix rule that fits an existing prefix to config_aggregation_list.json
4) (Discouraged) Add a language-specific rule to <lang>_config_rules.json

Once dd-go is updated, you can copy over the files to this repo and merge them in as part of your changes
This can be done by running the following from the src root

Usage: ./tests/telemetry_intake/update.sh
