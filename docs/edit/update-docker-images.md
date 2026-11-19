Some of images used in system-tests are prebuild and used threw [hub.docker.com/datadog/system-tests](https://hub.docker.com/repository/docker/datadog/system-tests/).

For weblog base images (every library with a `utils/build/docker/<library>/docker-bake.hcl`), publishing and
consumer selection use a two-step lock-file workflow:

1. GitLab CI's `build_base_images` job (`utils/base_images/build_base_images.py`) runs on every push, on every
   branch. For each target in a library's `docker-bake.hcl`, it derives the target's dependencies from the
   `COPY` instructions in its `<name>.base.Dockerfile` (see `docs/understand/weblogs/weblog-metadata.md`
   for the Dockerfile rules this relies on), computes a content hash of those dependencies, and, if a base
   image tagged with that hash doesn't already exist on both Docker Hub and the CI mirror
   (`registry.ddbuild.io/system-tests/mirror`), builds and pushes it as
   `<base tag>-<hash>`, as a multi-arch image (`linux/amd64` and `linux/arm64`): the
   `build_base_images_amd64` / `build_base_images_arm64` jobs build each architecture natively and
   push `<base tag>-<hash>-<arch>`, then `build_base_images` merges them into `<base tag>-<hash>`, on
   Docker Hub and in the mirror. If `utils/build/docker/base-images.lock.json` is stale, the job fails
   only after it has published all missing images.
2. After that publish job finishes, regenerate the lock:

   ```sh
   python utils/scripts/update-base-images-lock.py
   ```

   Commit `base-images.lock.json`. Base images are not listed in the `mirror_images*.yaml` files, so
   they don't need to be regenerated. The lock maps stable aliases such as
   `system_tests_base_nodejs_express4` to immutable content tags. Consumer Dockerfiles keep
   the stable alias in `FROM`; they do not change when base content changes.
3. GitHub Actions never builds these images itself. It resolves the consumer alias through
   the committed lock and polls Docker Hub for that real image before building the weblog.

The supported consumer build entrypoint is `./build.sh`, which supplies each locked image as
a BuildKit named context. A raw `docker build` command does not resolve these aliases.

For other prebuilt images (e.g. the proxy image), add the `build-proxy-image` label to your PR to force a
rebuild in GitHub CI; then, just before merging, ping somebody from Reliability & Performance team to push
your image to hub.docker.com (`#apm-shared-testing` on slack).
