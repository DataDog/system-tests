INFRA-001: Environment Variables at Scenario Level, Not in Dockerfiles
flag: Env vars that modify tracer/agent behavior should be set at the scenario level (`weblog_env`, `agent_env`), not in weblog Dockerfiles. Setting them in Dockerfiles affects all scenarios, not just the intended one.
detect: <TODO_RMM>
not when: <TODO_RMM>
ie good: <TODO_RMM>
ie bad: <TODO_RMM>
ref: [Scenarios](../../../utils/_context/_scenarios/__init__.py)

INFRA-002: Use Existing Utilities
flag: Do not redefine constants, enums, or helpers that already exist in `utils/`. In particular, check `utils/dd_constants.py` and `utils/_features.py` for constants and enums, and use `from utils._logger import logger`.
detect: <TODO_RMM>
not when: <TODO_RMM>
ie good: <TODO_RMM>
ie bad: <TODO_RMM>
ref: [Datadog constants](../../../utils/dd_constants.py), [Features](../../../utils/_features.py), [Using logger](../../edit/README.md#using-logger)

INFRA-003: Unique Weblog Names
flag: When adding a new weblog, verify the name is unique across all languages. Search existing weblogs under `utils/build/docker/` before using a name.
detect: <TODO_RMM>
not when: <TODO_RMM>
ie good: <TODO_RMM>
ie bad: <TODO_RMM>
ref: [Build documentation](../../execute/build.md)

INFRA-004: No Cross-Test-File Imports
flag: A `test_*.py` file must never import from another `test_*.py` file. If logic is shared between test files, it must be moved to a non-test utility module instead. Flag any PR that adds a cross-test import or a new exception to `.importlinter`.
detect: A PR adds a cross-test import or a new exception to `.importlinter`.
not when: <TODO_RMM>
ie good: <TODO_RMM>
ie bad: <TODO_RMM>
ref: [Repository structure rules](../../../.cursor/rules/repository-structure.mdc)

INFRA-005: Run cleanup when the job fails, not when it is cancelled.
flag: A tag, upload, or cleanup that must run after a failure uses `if: !cancelled()`, or a shell trap. Do not use `if: always()` unless that step must also run after a cancel. A missing `if` means `success()`, so a failed job skips the step. A tag may run before the work it names.
detect: A required upload, tag, or cleanup has no `if`, or it uses `if: always()`. In one `set -e` script it follows a command that can fail, and no trap runs it.
not when: The step must also run after a cancellation.
ie good: Use `if: !cancelled()`, or a shell trap.
ie bad: Leave the upload step without an `if`, so a failed build skips it. Use `if: always()`, so a cancelled job still uploads.
ref: [Official workflow tagging rules](../../../.cursor/rules/tag-official-workflows.mdc)

INFRA-006: Register a new base image in the CI mirror.
flag: If the mirror script skips a new image used by the build, extend that discovery in the same pull request.
detect: A new `FROM` image has no mirror entry, or the build bypasses the mirror.
not when: The image comes from `registry.ddbuild.io`.
ie good: Run `python utils/scripts/update_mirror_images.py` and commit the new mirror entry in the same pull request.
ie bad: Add `FROM python:3.12` with the mirror enabled and no mirror entry.
ref: [Update Docker images](../../edit/update-docker-images.md)

INFRA-007: Keep registry calls off the CI critical path.
flag: Use a base image so the job does not call a registry. If a base image cannot provide what the job needs, use a mirror. If a mirror is not possible, add a retry policy on the brittle command.
detect: A CI step pulls or installs from a registry on every run, and a base image already has those files. The pull skips a mirror that exists. The remaining registry command has no retry.
not when: <TODO_RMM>
ie good: Put the packages in the base image. If the job must fetch them, use the mirror. If no mirror exists, retry that command.
ie bad: Run `npm install` against the public registry in every job.

INFRA-008: Build test apps from locked dependency versions.
flag: A weblog or test-app image must install the dependencies it does not test from a committed lockfile or from exact pins. This also applies to transitive packages that the app uses directly. When the dependency inputs are unchanged, the build must not resolve new versions. A PR that adds or updates a dependency resolves it and commits the updated lock.
detect: A Dockerfile runs `bundle lock --update` or `npm update`. A manifest pins a package but leaves a related package open, and the lockfile does not lock it.
not when: A package follows the version of the SDK under test, or a range stays open on purpose to detect upstream drift, and a comment explains the exception.
ie good: Lock both `opentelemetry-sdk` and `opentelemetry-metrics-sdk`.
ie bad: Pin `opentelemetry-sdk`, leave `opentelemetry-metrics-sdk` open, and omit it from the lockfile.
