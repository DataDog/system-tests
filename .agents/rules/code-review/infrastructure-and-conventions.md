### INFRA-001: Environment Variables at Scenario Level, Not in Dockerfiles
- Severity: P1
- Flag: Env vars that modify tracer/agent behavior should be set at the scenario level (`weblog_env`, `agent_env`), not in weblog Dockerfiles. Setting them in Dockerfiles affects all scenarios, not just the intended one.
- Ref: [Scenarios](../../../utils/_context/_scenarios/__init__.py)

### INFRA-002: Use Existing Utilities
- Severity: P1
- Flag: Do not redefine constants, enums, or helpers that already exist in `utils/`. In particular, check `utils/dd_constants.py` and `utils/_features.py` for constants and enums, and use `from utils import logger`.
- Ref: [Datadog constants](../../../utils/dd_constants.py), [Features](../../../utils/_features.py), [Using logger](../../../docs/edit/README.md#using-logger)

### INFRA-003: Unique Weblog Names
- Severity: P0
- Flag: When adding a new weblog, verify the name is unique across all languages. Search existing weblogs under `utils/build/docker/` before using a name.
- Ref: [Build documentation](../../../docs/execute/build.md)

### INFRA-004: No Cross-Test-File Imports
- Severity: P0
- Flag: A `test_*.py` file must never import from another `test_*.py` file. If logic is shared between test files, it must be moved to a non-test utility module instead. Flag any PR that adds a cross-test import or a new exception to `.importlinter`.
- Detect: A PR adds a cross-test import or a new exception to `.importlinter`.
- Ref: [Repository structure rules](../repository-structure.md)

### INFRA-005: Run cleanup when the job fails, not when it is cancelled.
- Old_id: claude-08
- Severity: P1
- Flag: A tag, upload, or cleanup that must run after a failure uses `if: ${{ !cancelled() }}`, a quoted equivalent, or a shell trap. Do not use `if: always()` unless that step must also run after a cancel. A missing `if` means `success()`, so a failed job skips the step. A tag may run before the work it names.
- Detect: A required upload, tag, or cleanup has no `if`, or it uses `if: always()`. In one `set -e` script it follows a command that can fail, and no trap runs it.
- Not when: The step must also run after a cancellation.
- ✅ Use `if: ${{ !cancelled() }}`, or a shell trap.
- ❌ Leave the upload step without an `if`, so a failed build skips it. Use `if: always()`, so a cancelled job still uploads.
- Ref: [Official workflow tagging rules](../tag-official-workflows.md)

### INFRA-006: Register a new base image in the CI mirror.
- Old_id: codex-01
- Severity: P0
- Flag: If the mirror script skips a new image used by the build, extend that discovery in the same pull request.
- Detect: A new `FROM` image has no mirror entry, or the build bypasses the mirror.
- Not when: The image comes from `registry.ddbuild.io`.
- ✅ Run `python utils/scripts/update_mirror_images.py` and commit the new mirror entry in the same pull request.
- ❌ Add `FROM python:3.12` with the mirror enabled and no mirror entry.
- Ref: [Update Docker images](../../../docs/edit/update-docker-images.md)

### INFRA-007: Keep registry calls off the CI critical path.
- Old_id: claude-12
- Severity: P1
- Flag: Use a base image so the job does not call a registry. If a base image cannot provide what the job needs, use a mirror. If a mirror is not possible, add a retry policy on the brittle command.
- Detect: A CI step pulls or installs from a registry on every run, and a base image already has those files. The pull skips a mirror that exists. The remaining registry command has no retry.
- ✅ Put the packages in the base image. If the job must fetch them, use the mirror. If no mirror exists, retry that command.
- ❌ Run `npm install` against the public registry in every job.

### INFRA-008: Build test apps from locked dependency versions.
- Old_id: claude-15
- Severity: P0
- Flag: A weblog or test-app image must install the dependencies it does not test from a committed lockfile or from exact pins. This also applies to transitive packages that the app uses directly. When the dependency inputs are unchanged, the build must not resolve new versions. A PR that adds or updates a dependency resolves it and commits the updated lock.
- Detect: A Dockerfile runs `bundle lock --update` or `npm update`. A manifest pins a package but leaves a related package open, and the lockfile does not lock it.
- Not when: A package follows the version of the SDK under test, or a range stays open on purpose to detect upstream drift, and a comment explains the exception.
- ✅ Lock both `opentelemetry-sdk` and `opentelemetry-metrics-sdk`.
- ❌ Pin `opentelemetry-sdk`, leave `opentelemetry-metrics-sdk` open, and omit it from the lockfile.

### INFRA-009: Give new tooling paths a CI selection rule.
- Severity: P1
- Flag: A new folder or file that no test uses needs a rule in `utils/scripts/libraries_and_scenarios_rules.yml`. Without a rule, the CI selects every library and every scenario group for that path.
- Detect: The change adds a new path under `utils/scripts/` or at the repository root. No pattern in `libraries_and_scenarios_rules.yml` matches it, so the CI selects all scenario groups.
- Not when: The new files are framework code that tests use, such as `utils/_context/` or `utils/interfaces/`. Then the full run is the intended behavior.
- ✅ Add `utils/scripts/<tool>/*` with `scenario_groups: null` and `libraries: null`, and add a test in `tests/test_the_test/test_compute_libraries_and_scenarios.py`.
- ❌ Add `utils/scripts/<tool>/` with no rule, so the pull request runs the whole end-to-end CI.
- Ref: [libraries_and_scenarios_rules.yml](../../../utils/scripts/libraries_and_scenarios_rules.yml)

### INFRA-010: Keep the weblog specifications in sync with the code.
- Severity: P1
- Flag: A change to the interface of a weblog must update its specification in `docs/understand/weblogs/` in the same pull request. The code is the source of truth. The specifications are `end-to-end_weblog.md` (end-to-end endpoints), `parametric_weblog.md` (parametric HTTP interface), `graphql_weblog.md` (GraphQL weblogs), and `weblog-metadata.md` (`weblog_metadata.yml` format). An interface change adds, removes, or renames an endpoint. It also changes a request parameter, a response field, a status code, or an expected behavior.
- Detect: The diff changes an endpoint in a weblog under `utils/build/docker/<library>/`, in the parametric client `utils/docker_fixtures/_test_clients/_test_client_parametric.py`, or in the `weblog_metadata.yml` parser `utils/_context/weblog_metadata.py`, but not the matching specification. A test calls a new weblog endpoint that the specification does not list. The diff changes a specification so that it no longer matches the code.
- Not when: The change keeps the interface: an internal refactoring, a dependency bump, or a fix that makes a weblog follow its specification.
- ✅ Add the `/new_endpoint` route to the weblogs and its section to `end-to-end_weblog.md` in the same pull request.
- ❌ Add a field to the response of a parametric endpoint, and leave `parametric_weblog.md` unchanged.
- Ref: [Weblogs](../../../docs/understand/weblogs/README.md)

### INFRA-011: Keep local build output out of the Docker build context.
- Severity: P1
- Flag: A new weblog or test app that builds locally into a folder must exclude that folder in `.dockerignore`. Add the pattern in the same pull request. Examples are a cargo `target/`, a dotnet `bin/` or `obj/`, or a `node_modules/`.
- Detect: A new app under `utils/build/docker/` has a local build output folder, and no `.dockerignore` pattern excludes it.

### INFRA-013: Stop the session when a component fails to start.
- Severity: P1
- Flag: A failure to provision or start a scenario component must stop the session with an error. The framework must first keep the logs. It must not store the error and let the tests run.
- Detect: An error handler in `utils/` catches a startup or provisioning error and only logs or stores it. The session then continues to the test phase.
