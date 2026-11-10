# Docker Buildx bake file for Java base images
#
# `context` is always this directory: base image Dockerfiles only COPY files from
# here, so paths in the Dockerfile are relative to it (see build_base_images.py,
# which derives base_image_dependencies from these COPY instructions).

group "default" {
  targets = [
    "play",
    "ratpack",
    "vertx3",
    "vertx4",
  ]
}

target "_common" {
  context = "."
}

target "vertx3" {
  inherits   = ["_common"]
  dockerfile = "vertx3.base.Dockerfile"
  tags       = ["datadog/system-tests:vertx3.base"]
}

target "play" {
  inherits   = ["_common"]
  dockerfile = "play.base.Dockerfile"
  tags       = ["datadog/system-tests:play.base"]
}

target "ratpack" {
  inherits   = ["_common"]
  dockerfile = "ratpack.base.Dockerfile"
  tags       = ["datadog/system-tests:ratpack.base"]
}

target "vertx4" {
  inherits   = ["_common"]
  dockerfile = "vertx4.base.Dockerfile"
  tags       = ["datadog/system-tests:vertx4.base"]
}
