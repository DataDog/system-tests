# Docker Buildx bake file for java_otel base images
#
# `context` is always this directory: base image Dockerfiles only COPY files from
# here, so paths in the Dockerfile are relative to it (see build_base_images.py,
# which derives base_image_dependencies from these COPY instructions).

group "default" {
  targets = [
    "spring-boot-native",
    "spring-boot-otel",
  ]
}

target "_common" {
  context = "."
}

target "spring-boot-native" {
  inherits   = ["_common"]
  dockerfile = "spring-boot-native.base.Dockerfile"
  tags       = ["datadog/system-tests:java-otel-spring-boot-native.base"]
}

target "spring-boot-otel" {
  inherits   = ["_common"]
  dockerfile = "spring-boot-otel.base.Dockerfile"
  tags       = ["datadog/system-tests:java-otel-spring-boot-otel.base"]
}
