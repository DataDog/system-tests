# Docker Buildx bake file for Java base images
#
# `context` is always this directory: base image Dockerfiles only COPY files from
# here, so paths in the Dockerfile are relative to it (see build_base_images.py,
# which derives base_image_dependencies from these COPY instructions).

group "default" {
  targets = [
    "vertx3",
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
