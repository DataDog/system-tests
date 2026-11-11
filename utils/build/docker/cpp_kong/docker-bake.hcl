# Docker Buildx bake file for the Kong weblog base images.
#
# `context` is this directory. These Dockerfiles do not COPY repository files.

group "default" {
  targets = [
    "kong-build",
    "kong",
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

target "kong" {
  inherits   = ["_common"]
  dockerfile = "kong.base.Dockerfile"
  tags       = ["datadog/system-tests:kong.base"]
}
