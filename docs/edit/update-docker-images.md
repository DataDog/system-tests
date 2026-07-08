Some of images used in system-tests are prebuild and used threw [hub.docker.com/datadog/system-tests](https://hub.docker.com/repository/docker/datadog/system-tests/).

For weblog base images (nodejs, python, php), the build and push are fully automated:

1. GitLab CI's `build_base_images` job (`utils/scripts/build_base_images.py`) runs on every push, on every
   branch. For each `docker-bake.hcl` target declared in a library's `weblog_metadata.yml`
   `base_image_dependencies` section (see `docs/understand/weblogs/weblog-metadata.md`), it computes a
   content hash of the target's dependencies and, if a base image tagged with that hash doesn't already
   exist on Docker Hub, builds and pushes it as `<base tag>-<hash>`.
2. If you changed a file listed in `base_image_dependencies`, a new tag will automatically be pushed by
   that job. Update the `FROM` line of the relevant weblog Dockerfile(s) to point to the new tag (you can
   find it by running `python utils/scripts/build_base_images.py --dry-run` locally).
3. GitHub Actions never builds these images itself: it just waits (polling Docker Hub, with a timeout) for
   the tag referenced in the weblog's `FROM` line to become available before building the weblog, via
   `utils/scripts/wait_for_base_image.py`. So make sure the GitLab job has had a chance to push the new tag
   before (or shortly after) your PR's GitHub CI run starts.

For other prebuilt images (e.g. the proxy image), add the `build-proxy-image` label to your PR to force a
rebuild in GitHub CI; then, just before merging, ping somebody from Reliability & Performance team to push
your image to hub.docker.com (`#apm-shared-testing` on slack).
