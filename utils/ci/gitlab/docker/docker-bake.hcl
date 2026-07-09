# Docker Buildx bake file for the CI images built by the build_ci_image job
# (see .gitlab-ci.yml). Tags are passed in as variables computed from the
# content of each Dockerfile.

variable "IMAGE_BUILDER_TAG" {
  default = "latest"
}

variable "CI_RUNNER_TAG" {
  default = "latest"
}

group "default" {
  targets = ["image-builder", "ci-runner"]
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
