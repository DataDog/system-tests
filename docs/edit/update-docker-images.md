Some of images used in system-tests are prebuild and used threw [hub.docker.com/datadog/system-tests](https://hub.docker.com/repository/docker/datadog/system-tests/).

For weblog base images (nodejs, python, php), publishing and consumer selection use a
two-step lock-file workflow:

1. GitLab CI's `build_base_images` job (`utils/scripts/build-base-images.py`) runs on every push, on every
   branch. For each target in a library's `docker-bake.hcl`, it derives the target's dependencies from the
   `COPY` instructions in its `<name>.base.Dockerfile` (see `docs/understand/weblogs/weblog-metadata.md`
   for the Dockerfile rules this relies on), computes a content hash of those dependencies, and, if a base
   image tagged with that hash doesn't already exist on Docker Hub, builds and pushes it as
   `<base tag>-<hash>`. If `utils/build/docker/base-images.lock.json` is stale, the job fails
   only after it has published all missing images.
2. After that publish job finishes, regenerate the lock and mirror artifacts:

   ```sh
   python utils/scripts/build-base-images.py --update-lock
   python utils/scripts/update_mirror_images.py
   ```

   Commit `base-images.lock.json`, `mirror_images.yaml`, `mirror_images.lock.yaml`, and
   `utils/build/docker/buildkitd.toml`. The lock maps stable aliases such as
   `system_tests_base_nodejs_express4` to immutable content tags. Consumer Dockerfiles keep
   the stable alias in `FROM`; they do not change when base content changes.
3. GitHub Actions never builds these images itself. It resolves the consumer alias through
   the committed lock and polls Docker Hub for that real image before building the weblog.

The supported consumer build entrypoint is `./build.sh`, which supplies each locked image as
a BuildKit named context. A raw `docker build` command does not resolve these aliases.

For other prebuilt images (e.g. the proxy image), add the `build-proxy-image` label to your PR to force a
rebuild in GitHub CI; then, just before merging, ping somebody from Reliability & Performance team to push
your image to hub.docker.com (`#apm-shared-testing` on slack).
