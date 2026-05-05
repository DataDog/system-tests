# Docker Buildx bake file for php base images

group "default" {
  targets = [
    "php-fpm-8_0",
  ]
}

target "php-fpm-8_0" {
  context    = "."
  dockerfile = "utils/build/docker/php/php-fpm-8.0.base.Dockerfile"
  tags       = ["datadog/system-tests:php-fpm-8.0.base-v1"]
}
