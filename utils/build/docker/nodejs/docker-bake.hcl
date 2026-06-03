# Docker Buildx bake file for Node.js base images

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
  provenance = false
}

target "express4" {
  inherits   = ["_common"]
  context    = "."
  dockerfile = "utils/build/docker/nodejs/express4.base.Dockerfile"
  tags       = ["datadog/system-tests:express4.base-v2"]
}

target "express5" {
  inherits   = ["_common"]
  context    = "."
  dockerfile = "utils/build/docker/nodejs/express5.base.Dockerfile"
  tags       = ["datadog/system-tests:express5.base-v2"]
}

target "fastify" {
  inherits   = ["_common"]
  context    = "."
  dockerfile = "utils/build/docker/nodejs/fastify.base.Dockerfile"
  tags       = ["datadog/system-tests:fastify.base-v2"]
}

target "express4-typescript" {
  inherits   = ["_common"]
  context    = "."
  dockerfile = "utils/build/docker/nodejs/express4-typescript.base.Dockerfile"
  tags       = ["datadog/system-tests:express4-typescript.base-v1"]
}

target "nextjs" {
  inherits   = ["_common"]
  context    = "."
  dockerfile = "utils/build/docker/nodejs/nextjs.base.Dockerfile"
  tags       = ["datadog/system-tests:nextjs.base-v2"]
}
