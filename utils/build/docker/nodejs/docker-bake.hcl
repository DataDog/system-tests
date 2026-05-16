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
  tags       = ["ghcr.io/datadog/system-tests/weblog/nodejs:express4-v${VERSION}"]
  labels     = { "org.opencontainers.image.source" = "https://github.com/DataDog/system-tests" }
}

target "express5" {
  context    = "."
  dockerfile = "utils/build/docker/nodejs/express5.base.Dockerfile"
  tags       = ["ghcr.io/datadog/system-tests/weblog/nodejs:express5-v${VERSION}"]
  labels     = { "org.opencontainers.image.source" = "https://github.com/DataDog/system-tests" }
}

target "fastify" {
  context    = "."
  dockerfile = "utils/build/docker/nodejs/fastify.base.Dockerfile"
  tags       = ["ghcr.io/datadog/system-tests/weblog/nodejs:fastify-v${VERSION}"]
  labels     = { "org.opencontainers.image.source" = "https://github.com/DataDog/system-tests" }
}

target "express4-typescript" {
  context    = "."
  dockerfile = "utils/build/docker/nodejs/express4-typescript.base.Dockerfile"
  tags       = ["ghcr.io/datadog/system-tests/weblog/nodejs:express4-typescript-v${VERSION}"]
  labels     = { "org.opencontainers.image.source" = "https://github.com/DataDog/system-tests" }
}

target "nextjs" {
  context    = "."
  dockerfile = "utils/build/docker/nodejs/nextjs.base.Dockerfile"
  tags       = ["ghcr.io/datadog/system-tests/weblog/nodejs:nextjs-v${VERSION}"]
  labels     = { "org.opencontainers.image.source" = "https://github.com/DataDog/system-tests" }
}

target "anthropic-js" {
  context    = "."
  dockerfile = "utils/build/docker/nodejs/anthropic-js.base.Dockerfile"
  tags       = ["ghcr.io/datadog/system-tests/weblog/nodejs:anthropic-js-v${VERSION}"]
  labels     = { "org.opencontainers.image.source" = "https://github.com/DataDog/system-tests" }
}

target "openai-js" {
  context    = "."
  dockerfile = "utils/build/docker/nodejs/openai-js.base.Dockerfile"
  tags       = ["ghcr.io/datadog/system-tests/weblog/nodejs:openai-js-v${VERSION}"]
  labels     = { "org.opencontainers.image.source" = "https://github.com/DataDog/system-tests" }
}

target "google_genai-js" {
  context    = "."
  dockerfile = "utils/build/docker/nodejs/google_genai-js.base.Dockerfile"
  tags       = ["ghcr.io/datadog/system-tests/weblog/nodejs:google_genai-js-v${VERSION}"]
  labels     = { "org.opencontainers.image.source" = "https://github.com/DataDog/system-tests" }
}

target "parametric" {
  context    = "."
  dockerfile = "utils/build/docker/nodejs/parametric.base.Dockerfile"
  tags       = ["ghcr.io/datadog/system-tests/weblog/nodejs:parametric-v${VERSION}"]
  labels     = { "org.opencontainers.image.source" = "https://github.com/DataDog/system-tests" }
}
