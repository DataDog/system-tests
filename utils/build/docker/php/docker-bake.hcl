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
  context    = "utils/build/docker/php/"
  dockerfile = "php-fpm.base.Dockerfile"
  args       = { PHP_VERSION = "7.0" }
  tags       = ["datadog/system-tests:php-fpm-7.0.base-v1"]
}

target "php-fpm-7_1" {
  context    = "utils/build/docker/php"
  dockerfile = "php-fpm.base.Dockerfile"
  args       = { PHP_VERSION = "7.1" }
  tags       = ["datadog/system-tests:php-fpm-7.1.base-v1"]
}

target "php-fpm-7_2" {
  context    = "utils/build/docker/php"
  dockerfile = "php-fpm.base.Dockerfile"
  args       = { PHP_VERSION = "7.2" }
  tags       = ["datadog/system-tests:php-fpm-7.2.base-v1"]
}

target "php-fpm-7_3" {
  context    = "utils/build/docker/php"
  dockerfile = "php-fpm.base.Dockerfile"
  args       = { PHP_VERSION = "7.3" }
  tags       = ["datadog/system-tests:php-fpm-7.3.base-v1"]
}

target "php-fpm-7_4" {
  context    = "utils/build/docker/php"
  dockerfile = "php-fpm.base.Dockerfile"
  args       = { PHP_VERSION = "7.4" }
  tags       = ["datadog/system-tests:php-fpm-7.4.base-v1"]
}

target "php-fpm-8_0" {
  context    = "utils/build/docker/php"
  dockerfile = "php-fpm.base.Dockerfile"
  args       = { PHP_VERSION = "8.0" }
  tags       = ["datadog/system-tests:php-fpm-8.0.base-v1"]
}

target "php-fpm-8_1" {
  context    = "utils/build/docker/php"
  dockerfile = "php-fpm.base.Dockerfile"
  args       = { PHP_VERSION = "8.1" }
  tags       = ["datadog/system-tests:php-fpm-8.1.base-v1"]
}

target "php-fpm-8_2" {
  context    = "utils/build/docker/php"
  dockerfile = "php-fpm.base.Dockerfile"
  args       = { PHP_VERSION = "8.2" }
  tags       = ["datadog/system-tests:php-fpm-8.2.base-v1"]
}

target "php-fpm-8_5" {
  context    = "utils/build/docker/php"
  dockerfile = "php-fpm.base.Dockerfile"
  args       = { PHP_VERSION = "8.5" }
  tags       = ["datadog/system-tests:php-fpm-8.5.base-v1"]
}
