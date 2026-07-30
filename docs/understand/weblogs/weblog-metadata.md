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
> weblog Dockerfile and forget the `weblog_metadata.yml` entry, it is dropped before the CI
> matrix is even generated — it won't appear in the build matrix or any test job. This is
> exactly what happened in
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
  supported_scenarios: [SCENARIO_NAME, ...]  # optional; explicit opt-in, additive to categories (does not restrict them)
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
3. `categories` — for any other scenario, the weblog is included if it shares a category with it.

Note that `supported_scenarios` is additive, not restrictive: it only adds scenarios beyond
whatever category matching already grants — it never narrows down what `categories` matches. A
weblog with both fields set still matches every category-matched scenario, plus whatever is
listed in `supported_scenarios`.

### `categories`

A list of `WeblogCategory` values (defined in `utils/_context/constants.py`):

| Category | Meaning |
|----------|---------|
| `dd_trace` | Basic dd-trace instrumentation of an HTTP app |
| `dd_trace_graphql` | dd-trace instrumentation of a GraphQL app |
| `dd_trace_lambda` | dd-trace inside a lambda function |
| `dd_trace_frameworks` | dd-trace instrumentation of multi-language frameworks (mostly AI) |
| `open_telemetry` | Open Telemetry library |

`parametric` also exists on the enum, but it currently has no effect when used in a weblog's
`categories:` list: PARAMETRIC-flavored scenarios are selected through a separate mechanism
(`scenario.github_workflow`, unrelated to `WeblogMetaData`), so `support_scenario()` is never
consulted for them via this path. Adding `categories: [parametric]` to a real weblog would also
break `test_legacy_scenario_matrix` (the legacy matcher always returns `False` for non-endtoend
scenarios, so it would disagree with the new matcher). Treat it as reserved — don't use it.

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

## Base image dependencies

Base images (built by the `build_base_images` CI job, `utils/scripts/build_base_images.py`) are
declared in each library's `utils/build/docker/<library>/docker-bake.hcl`, one target per base
image. There is no separate dependency list to maintain: for each target, the job parses the
target's own `<name>.base.Dockerfile` and treats every `COPY` source as a dependency. This works
because base Dockerfiles are required to follow a few rules that make that derivation
unambiguous:

- No `ADD` — use `COPY` for everything (no glob sources, no whole-directory copies, no remote
  URLs).
- Every `COPY` has exactly one source: `COPY [flags] <source> <dest>`.
- The bake target's `context` is always the Dockerfile's own directory, so every `COPY` source
  is a plain path relative to that directory.
- No `RUN --mount` — a bind/cache/secret mount reads from a path the script can't see, so it
  would silently escape the derived dependency list.

(`COPY --from=<stage-or-image>` is unaffected: it isn't a local repository path, so it's skipped.)

The job computes a content hash from the resolved `docker-bake.hcl` target config, the target's
Dockerfile, and every git-tracked file under each derived dependency path, then pushes the base
image to Docker Hub tagged `<base-tag>-<hash12>` if that tag doesn't already exist. It never
overwrites an existing tag, so weblog Dockerfiles that `FROM` a base image must have their tag
updated by hand after a new one is pushed (run the script with `--dry-run` to find the current
tag for each target).

As a safety net, before building, every derived dependency is hardlinked (or copied, if
hardlinking isn't possible) into an isolated build context under `.base_image_build/`, and the
image is built from that directory instead of the real one. This way, if the Dockerfile
references a file the parser failed to recognize as a dependency, the build fails loudly
("file not found") instead of silently succeeding against the full checkout — which would leave
the tag's content hash stale without anyone noticing.

GitHub Actions never builds these base images itself: `utils/scripts/wait_for_base_image.py`
polls Docker Hub for the tag currently referenced in the weblog's `FROM` line (with a timeout)
before building the weblog, since GitLab CI is the only pipeline that builds and pushes them.
