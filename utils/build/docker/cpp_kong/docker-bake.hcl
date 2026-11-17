# Docker Buildx bake file for cpp_kong base images.
#
# `context` is this directory: base image Dockerfiles only COPY files from here.

group "default" {
  targets = [
    "kong-build",
    "kong-runtime",
  ]
}

target "_common" {
  context = "."
}

target "kong-build" {
  inherits   = ["_common"]
  dockerfile = "kong-build.base.Dockerfile"
  tags       = ["datadog/system-tests:kong-build.base"]
}

target "kong-runtime" {
  inherits   = ["_common"]
  dockerfile = "kong-runtime.base.Dockerfile"
  tags       = ["datadog/system-tests:kong-runtime.base"]
}
