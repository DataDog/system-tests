# Docker Buildx bake file for php base images

# Comma-separated list of platforms to build for (e.g. "linux/amd64,linux/arm64").
# Empty (default) builds only the host platform, which is required when using
# `docker buildx bake --load` for local iteration. CI passes both platforms when
# pushing so the published manifest covers amd64 and arm64.
variable "PLATFORMS" {
  default = ""
}

target "_common" {
  platforms = PLATFORMS == "" ? [] : split(",", PLATFORMS)
}

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

    "apache-mod-7_0",
    "apache-mod-7_1",
    "apache-mod-7_2",
    "apache-mod-7_3",
    "apache-mod-7_4",
    "apache-mod-8_0",
    "apache-mod-8_1",
    "apache-mod-8_2",

    "apache-mod-7_0-zts",
    "apache-mod-7_1-zts",
    "apache-mod-7_2-zts",
    "apache-mod-7_3-zts",
    "apache-mod-7_4-zts",
    "apache-mod-8_0-zts",
    "apache-mod-8_1-zts",
    "apache-mod-8_2-zts",
  ]
}

target "apache-mod-7_0" {
  inherits   = ["_common"]
  dockerfile = "utils/build/docker/php/apache-mod.base.Dockerfile"
  args       = { PHP_VERSION = "7.0", VARIANT = "release" }
  tags       = ["datadog/system-tests:apache-mod-7.0.base-v1"]
}

target "apache-mod-7_1" {
  inherits   = ["_common"]
  dockerfile = "utils/build/docker/php/apache-mod.base.Dockerfile"
  args       = { PHP_VERSION = "7.1", VARIANT = "release" }
  tags       = ["datadog/system-tests:apache-mod-7.1.base-v1"]
}

target "apache-mod-7_2" {
  inherits   = ["_common"]
  dockerfile = "utils/build/docker/php/apache-mod.base.Dockerfile"
  args       = { PHP_VERSION = "7.2", VARIANT = "release" }
  tags       = ["datadog/system-tests:apache-mod-7.2.base-v1"]
}

target "apache-mod-7_3" {
  inherits   = ["_common"]
  dockerfile = "utils/build/docker/php/apache-mod.base.Dockerfile"
  args       = { PHP_VERSION = "7.3", VARIANT = "release" }
  tags       = ["datadog/system-tests:apache-mod-7.3.base-v1"]
}

target "apache-mod-7_4" {
  inherits   = ["_common"]
  dockerfile = "utils/build/docker/php/apache-mod.base.Dockerfile"
  args       = { PHP_VERSION = "7.4", VARIANT = "release" }
  tags       = ["datadog/system-tests:apache-mod-7.4.base-v1"]
}

target "apache-mod-8_0" {
  inherits   = ["_common"]
  dockerfile = "utils/build/docker/php/apache-mod.base.Dockerfile"
  args       = { PHP_VERSION = "8.0", VARIANT = "release" }
  tags       = ["datadog/system-tests:apache-mod-8.0.base-v1"]
}

target "apache-mod-8_1" {
  inherits   = ["_common"]
  dockerfile = "utils/build/docker/php/apache-mod.base.Dockerfile"
  args       = { PHP_VERSION = "8.1", VARIANT = "release" }
  tags       = ["datadog/system-tests:apache-mod-8.1.base-v1"]
}

target "apache-mod-8_2" {
  inherits   = ["_common"]
  dockerfile = "utils/build/docker/php/apache-mod.base.Dockerfile"
  args       = { PHP_VERSION = "8.2", VARIANT = "release" }
  tags       = ["datadog/system-tests:apache-mod-8.2.base-v1"]
}

target "apache-mod-7_0-zts" {
  inherits   = ["_common"]
  dockerfile = "utils/build/docker/php/apache-mod.base.Dockerfile"
  args       = { PHP_VERSION = "7.0", VARIANT = "release-zts" }
  tags       = ["datadog/system-tests:apache-mod-7.0-zts.base-v1"]
}

target "apache-mod-7_1-zts" {
  inherits   = ["_common"]
  dockerfile = "utils/build/docker/php/apache-mod.base.Dockerfile"
  args       = { PHP_VERSION = "7.1", VARIANT = "release-zts" }
  tags       = ["datadog/system-tests:apache-mod-7.1-zts.base-v1"]
}

target "apache-mod-7_2-zts" {
  inherits   = ["_common"]
  dockerfile = "utils/build/docker/php/apache-mod.base.Dockerfile"
  args       = { PHP_VERSION = "7.2", VARIANT = "release-zts" }
  tags       = ["datadog/system-tests:apache-mod-7.2-zts.base-v1"]
}

target "apache-mod-7_3-zts" {
  inherits   = ["_common"]
  dockerfile = "utils/build/docker/php/apache-mod.base.Dockerfile"
  args       = { PHP_VERSION = "7.3", VARIANT = "release-zts" }
  tags       = ["datadog/system-tests:apache-mod-7.3-zts.base-v1"]
}

target "apache-mod-7_4-zts" {
  inherits   = ["_common"]
  dockerfile = "utils/build/docker/php/apache-mod.base.Dockerfile"
  args       = { PHP_VERSION = "7.4", VARIANT = "release-zts" }
  tags       = ["datadog/system-tests:apache-mod-7.4-zts.base-v1"]
}

target "apache-mod-8_0-zts" {
  inherits   = ["_common"]
  dockerfile = "utils/build/docker/php/apache-mod.base.Dockerfile"
  args       = { PHP_VERSION = "8.0", VARIANT = "release-zts" }
  tags       = ["datadog/system-tests:apache-mod-8.0-zts.base-v1"]
}

target "apache-mod-8_1-zts" {
  inherits   = ["_common"]
  dockerfile = "utils/build/docker/php/apache-mod.base.Dockerfile"
  args       = { PHP_VERSION = "8.1", VARIANT = "release-zts" }
  tags       = ["datadog/system-tests:apache-mod-8.1-zts.base-v1"]
}

target "apache-mod-8_2-zts" {
  inherits   = ["_common"]
  dockerfile = "utils/build/docker/php/apache-mod.base.Dockerfile"
  args       = { PHP_VERSION = "8.2", VARIANT = "release-zts" }
  tags       = ["datadog/system-tests:apache-mod-8.2-zts.base-v1"]
}

target "php-fpm-7_0" {
  inherits   = ["_common"]
  context    = "utils/build/docker/php/"
  dockerfile = "php-fpm.base.Dockerfile"
  args       = { PHP_VERSION = "7.0" }
  tags       = ["datadog/system-tests:php-fpm-7.0.base-v1"]
}

target "php-fpm-7_1" {
  inherits   = ["_common"]
  context    = "utils/build/docker/php"
  dockerfile = "php-fpm.base.Dockerfile"
  args       = { PHP_VERSION = "7.1" }
  tags       = ["datadog/system-tests:php-fpm-7.1.base-v1"]
}

target "php-fpm-7_2" {
  inherits   = ["_common"]
  context    = "utils/build/docker/php"
  dockerfile = "php-fpm.base.Dockerfile"
  args       = { PHP_VERSION = "7.2" }
  tags       = ["datadog/system-tests:php-fpm-7.2.base-v1"]
}

target "php-fpm-7_3" {
  inherits   = ["_common"]
  context    = "utils/build/docker/php"
  dockerfile = "php-fpm.base.Dockerfile"
  args       = { PHP_VERSION = "7.3" }
  tags       = ["datadog/system-tests:php-fpm-7.3.base-v1"]
}

target "php-fpm-7_4" {
  inherits   = ["_common"]
  context    = "utils/build/docker/php"
  dockerfile = "php-fpm.base.Dockerfile"
  args       = { PHP_VERSION = "7.4" }
  tags       = ["datadog/system-tests:php-fpm-7.4.base-v1"]
}

target "php-fpm-8_0" {
  inherits   = ["_common"]
  context    = "utils/build/docker/php"
  dockerfile = "php-fpm.base.Dockerfile"
  args       = { PHP_VERSION = "8.0" }
  tags       = ["datadog/system-tests:php-fpm-8.0.base-v1"]
}

target "php-fpm-8_1" {
  inherits   = ["_common"]
  context    = "utils/build/docker/php"
  dockerfile = "php-fpm.base.Dockerfile"
  args       = { PHP_VERSION = "8.1" }
  tags       = ["datadog/system-tests:php-fpm-8.1.base-v1"]
}

target "php-fpm-8_2" {
  inherits   = ["_common"]
  context    = "utils/build/docker/php"
  dockerfile = "php-fpm.base.Dockerfile"
  args       = { PHP_VERSION = "8.2" }
  tags       = ["datadog/system-tests:php-fpm-8.2.base-v1"]
}

target "php-fpm-8_5" {
  inherits   = ["_common"]
  context    = "utils/build/docker/php"
  dockerfile = "php-fpm.base.Dockerfile"
  args       = { PHP_VERSION = "8.5" }
  tags       = ["datadog/system-tests:php-fpm-8.5.base-v1"]
}
