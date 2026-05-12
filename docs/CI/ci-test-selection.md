# CI Test Selection

When a pull request is opened in the system-tests repository, the CI does not run
every test for every library. Instead, it looks at the files modified in the PR and
determines which **libraries** and **scenario groups** are relevant. This mechanism
is called *CI test selection*.

The selection rules live in
[`utils/scripts/libraries_and_scenarios_rules.yml`](../../utils/scripts/libraries_and_scenarios_rules.yml).
The file itself contains an embedded guide on syntax, ordering, and YAML pitfalls --
read it before making changes.

## How it works (short version)

1. The CI job **Compute libraries and scenarios** collects the list of files
   modified in the PR.
2. Each file is matched **top-down** against the patterns in
   `libraries_and_scenarios_rules.yml`. The **first match wins**.
3. The matched rule decides which libraries to build and which scenario groups to
   run.

The job prints a summary of the selected libraries and scenario groups at the end of
its output. It also emits **debug-level logs** showing which file matched which
pattern, which is helpful for troubleshooting unexpected selections.

## When should you edit the rules file?

- **You add a new file or directory** to the repo and want to control which tests
  the CI runs (or skips) when it is modified.
- **You want to disable CI for a path** (e.g. documentation, tooling) so that
  modifying it does not trigger any test run.
- **You need to change the test scope** associated with an existing path.

## Quick reference

Each entry maps a file pattern to the libraries and scenario groups to select:

```yaml
"some/path/*":
    libraries: [java, python]
    scenario_groups: [end_to_end]
```

| Field              | Missing (omitted)               | `null` or `[]`    | Explicit list          |
| ------------------ | ------------------------------- | ----------------- | ---------------------- |
| `libraries`        | Select **all** libraries        | Select **none**   | Select exactly those   |
| `scenario_groups`  | Select **all** groups (see [1]) | Select **none**   | Select exactly those   |
| `scenarios`        | Select **all** groups (see [1]) | Select **none**   | Select exactly those   |

[1] All scenario groups are selected only when **both** `scenario_groups` and
`scenarios` are omitted. If either one is present, only its value is used.

> Use `scenario_groups` when you want to target a category of scenarios, and
> `scenarios` when you need to target a single scenario by name. Valid scenario
> group names are listed in `utils/_context/_scenarios/core.py`.

**Important:** The `DEFAULT` scenario always runs on every selected library, even
if `scenario_groups` and `scenarios` are both set to `null`. In other words, as
long as at least one library is selected (explicitly or by omitting the field), the
DEFAULT scenario will be executed for it. To fully skip CI for a path, you must set
**both** `libraries: null` and `scenario_groups: null`.

### Common patterns

**Skip CI entirely** for a path (no libraries, no scenarios):

```yaml
"my/tooling/*":
    scenario_groups: null
    libraries: null
```

**Restrict to a single library**:

```yaml
"utils/build/docker/python/*":
    libraries: python
```

**Restrict to specific scenario groups**:

```yaml
"utils/docker_ssi/*":
    scenario_groups: docker_ssi
```

**Run everything** (default when both fields are omitted):

```yaml
"conftest.py":  # empty value -> all libraries, all scenario groups
```

## Debugging

The CI job **Compute libraries and scenarios** (in
`.github/workflows/compute_libraries_and_scenarios.yml`) outputs the final
selection at the end of its run. If the selection is not what you expect:

1. Open the job logs in GitHub Actions.
2. Look at the **Print results** step for the final computed values.
3. Look for `debug`-level log lines in the **Compute libraries and scenarios**
   step -- they show which pattern each modified file matched (or warn when no
   pattern matched, which causes all libraries/groups to be selected).

## Testing

Changes to the rules file are covered by unit tests in
`tests/test_the_test/test_compute_libraries_and_scenarios.py`.
