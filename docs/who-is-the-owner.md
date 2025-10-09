## System-tests repo: who owns what

This repo has many owners. Use the checklist below to find the right team.

* Inside `/tests/`
    * Check `.github/CODEOWNERS` first.
    * The `@features(...)` decorator on a test class/method names the precise owner.
* Inside `/utils/build/docker/<lang>/`
    * Owned by the corresponding `<lang>` guild.
* Everything else
    * Owned by `@DataDog/system-tests-core`.
