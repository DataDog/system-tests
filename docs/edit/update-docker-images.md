Some of images used in system-tests are prebuild and used threw [hub.docker.com/datadog/system-tests](https://hub.docker.com/repository/docker/datadog/system-tests/).

If you need to update them, you will need to follow those

1. update the version in the tag for the image you've just modified (there should be 3 or 4 occurences in the code)
1. create your PR, and add the relevant label to rebuild the image in the CI

- `build-python-base-images` for python weblogs
- `build-proxy-image` for proxy image

3. just before merging your PR, ping somebody from Reliability & Performance team to push your image to hub.docker.com (`#apm-shared-testing` on slack)
