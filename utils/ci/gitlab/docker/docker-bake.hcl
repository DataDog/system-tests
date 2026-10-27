# Docker Buildx bake file for the CI images built by the build_ci_image job
# (see .gitlab-ci.yml). Tags are passed in as variables computed from the
# content of each Dockerfile.
#
# build_ci_image.py overrides the tags and platform of each target: ci-runner is built
# natively once per architecture, then merged into a multi-arch image (as are proxy and internal_server).

variable "IMAGE_BUILDER_TAG" {
  default = "latest"
}

variable "CI_RUNNER_TAG" {
  default = "latest"
}

group "default" {
  targets = ["image-builder", "ci-runner", "proxy", "internal_server"]
}

target "_common" {
  context    = "."
  platforms  = ["linux/amd64"]
  provenance = false
}

target "image-builder" {
  inherits   = ["_common"]
  dockerfile = "utils/ci/gitlab/docker/image-builder.Dockerfile"
  tags       = ["registry.ddbuild.io/system-tests/image-builder:${IMAGE_BUILDER_TAG}"]
}

target "ci-runner" {
  inherits   = ["_common"]
  dockerfile = "utils/ci/gitlab/docker/system-tests.Dockerfile"
  tags       = ["registry.ddbuild.io/system-tests/ci-runner:${CI_RUNNER_TAG}"]
}

target "proxy" {
  inherits   = ["_common"]
  dockerfile = "utils/build/docker/proxy.Dockerfile"
  tags       = ["registry.ddbuild.io/system-tests/proxy:latest"]
}

target "internal_server" {
  inherits   = ["_common"]
  dockerfile = "utils/build/docker/internal_server.Dockerfile"
  tags       = ["registry.ddbuild.io/system-tests/internal_server:latest"]
}
