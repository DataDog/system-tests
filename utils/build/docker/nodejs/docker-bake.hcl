# Docker Buildx bake file for Node.js base images
#
# `context` is always this directory: base image Dockerfiles only COPY files from
# here, so paths in the Dockerfile are relative to it (see build_base_images.py,
# which derives base_image_dependencies from these COPY instructions).

group "default" {
  targets = [
    "express4",
    "express5",
    "fastify",
    "express4-typescript",
    "nextjs",
  ]
}

target "_common" {
  context    = "."
  provenance = false
}

target "express4" {
  inherits   = ["_common"]
  dockerfile = "express4.base.Dockerfile"
  tags       = ["datadog/system-tests:express4.base"]
}

target "express5" {
  inherits   = ["_common"]
  dockerfile = "express5.base.Dockerfile"
  tags       = ["datadog/system-tests:express5.base"]
}

target "fastify" {
  inherits   = ["_common"]
  dockerfile = "fastify.base.Dockerfile"
  tags       = ["datadog/system-tests:fastify.base"]
}

target "express4-typescript" {
  inherits   = ["_common"]
  dockerfile = "express4-typescript.base.Dockerfile"
  tags       = ["datadog/system-tests:express4-typescript.base"]
}

target "nextjs" {
  inherits   = ["_common"]
  dockerfile = "nextjs.base.Dockerfile"
  tags       = ["datadog/system-tests:nextjs.base"]
}
