# Weblog metadata

Each library folder under `utils/build/docker/<library>/` may contain a `weblog_metadata.yml` file
that declares metadata for weblogs that cannot be inferred from the Dockerfile alone.

## When to add an entry

A weblog discovered via a `<name>.Dockerfile` file defaults to `build_mode: prebuild`, no
`framework_versions`, and **no `categories`**. Add an entry to override those defaults, and — see
the warning below — to make sure the weblog actually runs somewhere.

> **A weblog with no `categories` and no `supported_scenarios` matches zero scenarios.**
> Scenario matching is deny-by-default: a weblog only runs in a scenario if they share a
> category, or the scenario is explicitly listed in `supported_scenarios`. If you add a new
> weblog Dockerfile and forget the `weblog_metadata.yml` entry, it will build in CI but never
> be selected for any test. This is exactly what happened in
> [#7077](https://github.com/DataDog/system-tests/pull/7077): the `net-http-span-pool` golang
> weblog was added via Dockerfile only, with no `categories`, and silently ran in zero scenarios.
> It was only caught because a legacy allow-by-default matcher is still kept around for parity
> checks (`test_legacy_scenario_matrix` in `tests/test_the_test/test_ci_orchestrator.py`) — once
> that test is removed, this mistake will go undetected. **When adding a new weblog, always
> declare at least one `categories` entry or a `supported_scenarios` list.**

## Format

```yaml
<weblog-name>:
  build_mode: none | local | prebuild        # default: prebuild
  framework_versions: ["1.0.0", ...]         # optional; omit for non-integration-framework weblogs
  categories: [dd_trace, ...]                # optional; see "Scenario matching" below — default: [] (matches nothing)
  supported_scenarios: [SCENARIO_NAME, ...]  # optional; explicit allow-list, takes precedence over categories
  excluded_scenarios: [SCENARIO_NAME, ...]   # optional; explicit deny-list, takes precedence over everything
```

The `library` field is intentionally absent — it is inferred from the folder the file lives in.

## `build_mode` values

| Value | Meaning |
|-------|---------|
| `none` | No Docker build. The shared `binaries_artifact` is used as-is (integration frameworks, proxies). |
| `local` | The weblog has a fully baked base image. The build step inside the test job is trivial (only `COPY` instructions). No dedicated CI build job. |
| `prebuild` | Built ahead of time by a dedicated `build_end_to_end` CI job that uploads a per-weblog artifact; still built locally when the test job runs. |

Both `local` and `prebuild` set `weblog_build_required = true`.

## Scenario matching: `categories`, `supported_scenarios`, `excluded_scenarios`

Each `Scenario` declares which `WeblogCategory` values it accepts (`Scenario.weblog_categories`,
set per-scenario in `utils/_context/_scenarios/*.py` and re-exported from
`utils/_context/_scenarios/__init__.py`). A weblog is selected for a scenario if it shares
at least one category with it — unless `supported_scenarios` or `excluded_scenarios` override
that decision. The precedence, from `WeblogMetaData.support_scenario` in
`utils/_context/weblog_metadata.py`, is:

1. `excluded_scenarios` — if the scenario name is listed here, the weblog is excluded, full stop.
2. `supported_scenarios` — if the scenario name is listed here, the weblog is included, even if
   no category matches.
3. `categories` — otherwise, the weblog is included only if it shares a category with the scenario.

### `categories`

A list of `WeblogCategory` values (defined in `utils/_context/constants.py`):

| Category | Meaning |
|----------|---------|
| `dd_trace` | Basic dd-trace instrumentation of an HTTP app |
| `dd_trace_graphql` | dd-trace instrumentation of a GraphQL app |
| `dd_trace_lambda` | dd-trace inside a lambda function |
| `dd_trace_frameworks` | dd-trace instrumentation of multi-language frameworks (mostly AI) |
| `open_telemetry` | Open Telemetry library |
| `parametric` | Weblog shipping a dd-trace library with an interface dedicated to the PARAMETRIC scenario |

### `supported_scenarios` / `excluded_scenarios`

Lists of scenario names (e.g. `DEFAULT`, `APPSEC_BLOCKING`, `GRAPHQL_ERROR_TRACKING`) used when
category matching isn't precise enough — either to opt a weblog into a scenario outside its
categories, or to opt it out of one inside them.

Examples from `utils/build/docker/golang/weblog_metadata.yml`:

```yaml
net-http:
  categories: [dd_trace]        # runs in every scenario that accepts dd_trace weblogs

graphql-go:
  categories: [dd_trace_graphql]
  excluded_scenarios: [GRAPHQL_ERROR_TRACKING]   # runs in dd_trace_graphql scenarios, except this one

haproxy:
  build_mode: none
  supported_scenarios: [APPSEC_BLOCKING, DEFAULT]  # no categories at all; runs only in these two,
                                                    # by explicit name
```

## Integration-framework weblogs

When `framework_versions` is set, a single entry fans out into one weblog per version at load time:

```yaml
openai-js:
  build_mode: none
  framework_versions: ["6.0.0", "7.0.0"]
```

produces `openai-js@6.0.0` and `openai-js@7.0.0`.

## Loader

`WeblogMetaData.load(library)` in `utils/_context/weblog_metadata.py` merges:
1. Weblogs discovered from `*.Dockerfile` files in the library folder (default metadata).
2. Explicit overrides from `weblog_metadata.yml`.
