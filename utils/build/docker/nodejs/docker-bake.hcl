# Docker Buildx bake file for Node.js base images

variable "VERSION" {
  default = "latest"
}

group "default" {
  targets = [
    "express4",
    "express5",
    "fastify",
    "express4-typescript",
    "nextjs",
    "anthropic-js",
    "openai-js",
    "google_genai-js",
    "parametric",
  ]
}

target "express4" {
  context    = "."
  dockerfile = "utils/build/docker/nodejs/express4.base.Dockerfile"
  tags       = ["ghcr.io/datadog/system-tests:express4.base-v${VERSION}"]
  labels     = { "org.opencontainers.image.source" = "https://github.com/DataDog/system-tests" }
}

target "express5" {
  context    = "."
  dockerfile = "utils/build/docker/nodejs/express5.base.Dockerfile"
  tags       = ["ghcr.io/datadog/system-tests:express5.base-v${VERSION}"]
  labels     = { "org.opencontainers.image.source" = "https://github.com/DataDog/system-tests" }
}

target "fastify" {
  context    = "."
  dockerfile = "utils/build/docker/nodejs/fastify.base.Dockerfile"
  tags       = ["ghcr.io/datadog/system-tests:fastify.base-v${VERSION}"]
  labels     = { "org.opencontainers.image.source" = "https://github.com/DataDog/system-tests" }
}

target "express4-typescript" {
  context    = "."
  dockerfile = "utils/build/docker/nodejs/express4-typescript.base.Dockerfile"
  tags       = ["ghcr.io/datadog/system-tests:express4-typescript.base-v${VERSION}"]
  labels     = { "org.opencontainers.image.source" = "https://github.com/DataDog/system-tests" }
}

target "nextjs" {
  context    = "."
  dockerfile = "utils/build/docker/nodejs/nextjs.base.Dockerfile"
  tags       = ["ghcr.io/datadog/system-tests:nextjs.base-v${VERSION}"]
  labels     = { "org.opencontainers.image.source" = "https://github.com/DataDog/system-tests" }
}

target "anthropic-js" {
  context    = "."
  dockerfile = "utils/build/docker/nodejs/anthropic-js.base.Dockerfile"
  tags       = ["ghcr.io/datadog/system-tests:anthropic-js.base-v${VERSION}"]
  labels     = { "org.opencontainers.image.source" = "https://github.com/DataDog/system-tests" }
}

target "openai-js" {
  context    = "."
  dockerfile = "utils/build/docker/nodejs/openai-js.base.Dockerfile"
  tags       = ["ghcr.io/datadog/system-tests:openai-js.base-v${VERSION}"]
  labels     = { "org.opencontainers.image.source" = "https://github.com/DataDog/system-tests" }
}

target "google_genai-js" {
  context    = "."
  dockerfile = "utils/build/docker/nodejs/google_genai-js.base.Dockerfile"
  tags       = ["ghcr.io/datadog/system-tests:google_genai-js.base-v${VERSION}"]
  labels     = { "org.opencontainers.image.source" = "https://github.com/DataDog/system-tests" }
}

target "parametric" {
  context    = "."
  dockerfile = "utils/build/docker/nodejs/parametric.base.Dockerfile"
  tags       = ["ghcr.io/datadog/system-tests:parametric-nodejs.base-v${VERSION}"]
  labels     = { "org.opencontainers.image.source" = "https://github.com/DataDog/system-tests" }
}
