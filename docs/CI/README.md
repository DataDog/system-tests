All information you need to add System Tests in your CI.

## How to integrate in a CI?

You'll need a CI that with `docker` and `python 3.12` installed, among with very common UNIX tools.

1. Clone this repo
2. Copy paste your components' build inside `./binaries` (See [binaries documentation](../execute/binaries.md))
3. `./build.sh` with relevant `library` (see [build documentation](../execute/build.md)). Example: `./build.sh java`
4. `./run.sh`

You will find different template or example:

* [GitHub Actions](./github-actions.md)
* GitLab CI: WIP -- see below
* [Azure](https://github.com/DataDog/dd-trace-dotnet/blob/master/.azure-pipelines/ultimate-pipeline.yml) (look for `stage: system_tests`)

### GitLab CI secrets setup

1. Install aws-cli
2. Save a valid github PATH token in a file named GH_TOKEN
3. then execute

```
aws-vault exec --debug build-stable-developer  # Enter a token from your MFA device
unset AWS_VAULT
cat GH_TOKEN | aws-vault exec build-stable-developer -- ci-secrets set ci.system-tests.gh_token
```

---

## In this section

- [GitHub Actions](./github-actions.md) -- GitHub Actions workflow details
- [System-tests CI](./system-tests-ci.md) -- how the system-tests own CI pipeline works

## See also

- [Running tests](../execute/README.md) -- build and run options
- [CI and scenarios](./system-tests-ci.md#scenario-detection-in-ci) -- how scenarios are wired into CI
- [Back to documentation index](../README.md)
