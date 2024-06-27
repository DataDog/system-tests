All information you need to add System Tests in your CI.

## How to integrate in a CI?

You'll need a CI that with `docker` and `python 3.11` installed, among with very common UNIX tools.

A valid `DD_API_KEY` env var for staging must be set.

1. Clone this repo
2. Copy paste your components' build inside `./binaries` (See [documentation](./binaries.md))
3. `./build.sh` with relevant `library` (see [documentation](../execute/build.md)). Exemple: `./build.sh java`
4. `./run.sh`

You will find different template or example:

* [github actions](./github-actions.md)
* [gitlab CI](./gitlab-ci.md): TODO
* [azure](https://github.com/DataDog/dd-trace-dotnet/blob/master/.azure-pipelines/ultimate-pipeline.yml) (look for `stage: system_tests`)
