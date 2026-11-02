## 6. Environment Variables at Scenario Level, Not in Dockerfiles

Env vars that modify tracer/agent behavior should be set at the scenario level (`weblog_env`, `agent_env`), not in weblog Dockerfiles. Setting them in Dockerfiles affects all scenarios, not just the intended one.

- Ref: [scenarios](mdc:utils/_context/_scenarios/__init__.py)

## 7. Use Existing Utilities

Do not redefine constants, enums, or helpers that already exist in `utils/`. In particular:

- Constants/enums: check `utils/dd_constants.py` and `utils/_features.py`
- Logger: use `from utils._logger import logger` — see [Using logger](mdc:docs/edit/README.md)

## 9. Unique Weblog Names

When adding a new weblog, verify the name is unique across all languages. Search existing weblogs under `utils/build/docker/` before using a name.

- Ref: [build.md](mdc:docs/execute/build.md)

## 10. No Cross-Test-File Imports

A `test_*.py` file must never import from another `test_*.py` file. If logic is shared between test files, it must be moved to a non-test utility module instead. Flag any PR that adds a cross-test import or a new exception to `.importlinter`.

- Ref: [repository-structure.mdc](mdc:.cursor/rules/repository-structure.mdc), enforced by the `Test files do not import other test files` Import Linter contract

ID: claude-08

Title: Run cleanup when the job fails, not when it is cancelled.

Rule: A tag, upload, or cleanup that must run after a failure uses `if: !cancelled()`, or a shell trap. Do not use `if: always()` unless that step must also run after a cancel. A missing `if` means `success()`, so a failed job skips the step. A tag may run before the work it names.

Why: `success()` skips the step when the job fails, so the tag or the upload never happens. `always()` also runs that step after a cancel. The tag rule is in https://github.com/DataDog/system-tests/blob/main/.cursor/rules/tag-official-workflows.mdc.

Detect: A required upload, tag, or cleanup has no `if`, or it uses `if: always()`. In one `set -e` script it follows a command that can fail, and no trap runs it.

Example: Bad: the upload step has no `if`, so a failed build skips it. Bad: `if: always()`, so a cancelled job still uploads. Good: `if: !cancelled()`, or a shell trap runs the upload.

Evidence:

• https://github.com/DataDog/system-tests/pull/7945#discussion_r4185536137
• https://github.com/DataDog/system-tests/pull/7945#discussion_r4185832459

ID: codex-01

Title: Register a new base image in the CI mirror.

Rule: Follow https://github.com/DataDog/system-tests/blob/main/docs/edit/update-docker-images.md when the build uses the image mirror. If the mirror script skips the new image, extend that discovery in the same pull request. An image from registry.ddbuild.io needs no mirror entry.

Why: CI may have no credentials for a public registry. The new image must arrive through the mirror.

Detect: A new `FROM` image has no mirror entry, or the build bypasses the mirror. An image from registry.ddbuild.io is not a miss.

Example: Bad: `FROM python:3.12` with the mirror on and no mirror entry. Good: the same pull request runs `python utils/scripts/update_mirror_images.py` and commits the new mirror entry.

Evidence:

• https://github.com/DataDog/system-tests/pull/8121#pullrequestreview-5596645236
• https://github.com/DataDog/system-tests/pull/8121#issuecomment-6311179919

ID: claude-12

Title:  Keep registry calls off the CI critical path.

Rule: Use a base image so the job does not call a registry. If a base image cannot provide what the job needs, use a mirror. If a mirror is not possible, add a retry policy on the brittle command.

Why: A registry call can fail for a reason outside the change. A base image removes the call. A mirror or a retry limits the damage when the call remains.

Detect: A CI step pulls or installs from a registry on every run, and a base image already has those files. The pull skips a mirror that exists. The remaining registry command has no retry.

Example: Bad: every job runs `npm install` against the public registry. Good: those packages are already in the base image. If the job must fetch them, it uses the mirror. If no mirror exists, that command retries.

Evidence:

• https://github.com/DataDog/system-tests/pull/8175
• https://github.com/DataDog/system-tests/pull/8039

ID: claude-15

Title: Build test apps from locked dependency versions.

Rule: A weblog or test-app image must install the dependencies it does not test from a committed lockfile or from exact pins. This also applies to transitive packages that the app uses directly. When the dependency inputs are unchanged, the build must not resolve new versions. A PR that adds or updates a dependency resolves it and commits the updated lock. Two exceptions are allowed when a comment explains them. A package can follow the version of the SDK under test, or a range can stay open on purpose to detect upstream drift.

Why: A dependency release between two CI runs changes the app without any commit. Tests then fail for reasons that look like tracer bugs.

Detect: A Dockerfile runs `bundle lock --update` or `npm update`. A manifest pins a package but leaves a related package open, and the lockfile does not lock it.

Example: Bad: the Gemfile pins `opentelemetry-sdk` but leaves `opentelemetry-metrics-sdk` open, and the lockfile does not lock it. Good: the lockfile locks both gems.

Evidence:

• https://github.com/DataDog/system-tests/pull/7174
• https://github.com/DataDog/system-tests/pull/7641
• https://github.com/DataDog/system-tests/pull/8090
