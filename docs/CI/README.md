All information you need to add System Tests in your CI.

## How to integrate in a CI?

You'll need a CI that with `docker` and `python 3.12` installed, among with very common UNIX tools.

1. Clone this repo
2. Copy paste your components' build inside `./binaries` (See [binaries documentation](../execute/binaries.md))
3. `./build.sh` with relevant `library` (see [build documentation](../execute/build.md)). Example: `./build.sh java`
4. `./run.sh`

You will find different template or example:

* [GitHub Actions](./github-actions.md)
* [GitLab CI](./gitlab-ci.md): TODO
* [Azure](https://github.com/DataDog/dd-trace-dotnet/blob/master/.azure-pipelines/ultimate-pipeline.yml) (look for `stage: system_tests`)

---

## In this section

- [GitHub Actions](./github-actions.md) -- GitHub Actions workflow details
- [GitLab CI](./gitlab-ci.md) -- GitLab CI setup
- [System-tests CI](./system-tests-ci.md) -- how the system-tests own CI pipeline works

## See also

- [Running tests](../execute/README.md) -- build and run options
- [CI and scenarios](../edit/CI-and-scenarios.md) -- how scenarios are wired into CI
- [Back to documentation index](../README.md)
