All information you need to add System Tests in your CI.

## How to integrate in a CI?

You'll need a CI that supports `docker-compose`, and very common UNIX tools.

A valid `DD_API_KEY` env var for staging must be set. 

1. Clone this repo
2. Copy paste your components' build inside `./binaries` (See [documentation](./binaries.md))
3. `./build.sh` with relevant `library` (see [documentation](../execute/build.md)). Exemple: `./build.sh -l java`
4. `./run.sh`

You will find different template:

* [github actions](./github-actions.md)
* [gitlab CI](./gitlab-ci.md): TODO
* azure: TODO
* jenkins: TODO
