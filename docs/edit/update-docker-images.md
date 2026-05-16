Some images used in system-tests are pre-built and published to a registry.

## Python and PHP base images

Published to [hub.docker.com/datadog/system-tests](https://hub.docker.com/repository/docker/datadog/system-tests/).

1. Update the version tag for the image you modified (there should be 3 or 4 occurrences in the code).
2. Open a PR and add the relevant label to rebuild the image in CI:
   * `build-python-base-images` for Python weblogs
   * `build-php-base-images` for PHP weblogs
   * `build-proxy-image` for the proxy image
3. Just before merging, ping someone from the Reliability & Performance team to push the image to hub.docker.com (`#apm-shared-testing` on Slack).

## Node.js base images

Published to [ghcr.io/datadog/system-tests](https://github.com/orgs/DataDog/packages?repo_name=system-tests). The push happens automatically in CI — no manual step needed.

1. Open a PR.
2. Update the version tag in all `FROM` lines for the images you modified, using the PR number as the version (e.g. `ghcr.io/datadog/system-tests:express4.base-v6903` for PR #6903). There should be one occurrence per affected weblog Dockerfile.
3. Add the `build-nodejs-base-images` label to the PR.
4. Push a commit — CI will automatically build and publish the images to GHCR.
