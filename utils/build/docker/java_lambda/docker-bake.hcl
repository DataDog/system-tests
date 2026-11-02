# Docker Buildx bake file for java_lambda base images
#
# `context` is always this directory: base image Dockerfiles only COPY files from
# here, so paths in the Dockerfile are relative to it (see build_base_images.py,
# which derives base_image_dependencies from these COPY instructions).

group "default" {
  targets = [
    "runtime",
  ]
}

target "_common" {
  context = "."
}

target "runtime" {
  inherits   = ["_common"]
  dockerfile = "runtime.base.Dockerfile"
  tags       = ["datadog/system-tests:java-lambda-runtime.base"]
}
