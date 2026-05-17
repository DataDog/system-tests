# Docker Buildx bake file for Node.js base images

group "default" {
  targets = [
    "express4",
    "express5",
    "fastify",
    "express4-typescript",
    "nextjs",
    "parametric",
  ]
}

target "express4" {
  context    = "."
  dockerfile = "utils/build/docker/nodejs/express4.base.Dockerfile"
  tags       = ["datadog/system-tests:express4.base-v1"]
}

target "express5" {
  context    = "."
  dockerfile = "utils/build/docker/nodejs/express5.base.Dockerfile"
  tags       = ["datadog/system-tests:express5.base-v1"]
}

target "fastify" {
  context    = "."
  dockerfile = "utils/build/docker/nodejs/fastify.base.Dockerfile"
  tags       = ["datadog/system-tests:fastify.base-v1"]
}

target "express4-typescript" {
  context    = "."
  dockerfile = "utils/build/docker/nodejs/express4-typescript.base.Dockerfile"
  tags       = ["datadog/system-tests:express4-typescript.base-v1"]
}

target "nextjs" {
  context    = "."
  dockerfile = "utils/build/docker/nodejs/nextjs.base.Dockerfile"
  tags       = ["datadog/system-tests:nextjs.base-v1"]
}

target "parametric" {
  context    = "."
  dockerfile = "utils/build/docker/nodejs/parametric.base.Dockerfile"
  tags       = ["datadog/system-tests:parametric-nodejs.base-v1"]
}
