# Docker Buildx bake file for php base images

group "default" {
  targets = [
    "php-fpm-7_0",
    "php-fpm-7_1",
    "php-fpm-7_2",
    "php-fpm-7_3",
    "php-fpm-7_4",
    "php-fpm-8_0",
    "php-fpm-8_1",
    "php-fpm-8_2",
    "php-fpm-8_5",
  ]
}

target "php-fpm-7_0" {
  context    = "."
  dockerfile = "utils/build/docker/php/php-fpm-7.0.base.Dockerfile"
  tags       = ["datadog/system-tests:php-fpm-7.0.base-v1"]
}

target "php-fpm-7_1" {
  context    = "."
  dockerfile = "utils/build/docker/php/php-fpm-7.1.base.Dockerfile"
  tags       = ["datadog/system-tests:php-fpm-7.1.base-v1"]
}

target "php-fpm-7_2" {
  context    = "."
  dockerfile = "utils/build/docker/php/php-fpm-7.2.base.Dockerfile"
  tags       = ["datadog/system-tests:php-fpm-7.2.base-v1"]
}

target "php-fpm-7_3" {
  context    = "."
  dockerfile = "utils/build/docker/php/php-fpm-7.3.base.Dockerfile"
  tags       = ["datadog/system-tests:php-fpm-7.3.base-v1"]
}

target "php-fpm-7_4" {
  context    = "."
  dockerfile = "utils/build/docker/php/php-fpm-7.4.base.Dockerfile"
  tags       = ["datadog/system-tests:php-fpm-7.4.base-v1"]
}

target "php-fpm-8_0" {
  context    = "."
  dockerfile = "utils/build/docker/php/php-fpm-8.0.base.Dockerfile"
  tags       = ["datadog/system-tests:php-fpm-8.0.base-v1"]
}

target "php-fpm-8_1" {
  context    = "."
  dockerfile = "utils/build/docker/php/php-fpm-8.1.base.Dockerfile"
  tags       = ["datadog/system-tests:php-fpm-8.1.base-v1"]
}

target "php-fpm-8_2" {
  context    = "."
  dockerfile = "utils/build/docker/php/php-fpm-8.2.base.Dockerfile"
  tags       = ["datadog/system-tests:php-fpm-8.2.base-v1"]
}

target "php-fpm-8_5" {
  context    = "."
  dockerfile = "utils/build/docker/php/php-fpm-8.5.base.Dockerfile"
  tags       = ["datadog/system-tests:php-fpm-8.5.base-v1"]
}
