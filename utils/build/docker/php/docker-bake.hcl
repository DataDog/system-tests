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

target "_common" {
  context = "."
}

target "apache-mod-7_0" {
  inherits   = ["_common"]
  dockerfile = "apache-mod.base.Dockerfile"
  args       = { PHP_VERSION = "7.0", VARIANT = "release" }
  tags       = ["datadog/system-tests:apache-mod-7.0.base"]
}

target "apache-mod-7_1" {
  inherits   = ["_common"]
  dockerfile = "apache-mod.base.Dockerfile"
  args       = { PHP_VERSION = "7.1", VARIANT = "release" }
  tags       = ["datadog/system-tests:apache-mod-7.1.base"]
}

target "apache-mod-7_2" {
  inherits   = ["_common"]
  dockerfile = "apache-mod.base.Dockerfile"
  args       = { PHP_VERSION = "7.2", VARIANT = "release" }
  tags       = ["datadog/system-tests:apache-mod-7.2.base"]
}

target "apache-mod-7_3" {
  inherits   = ["_common"]
  dockerfile = "apache-mod.base.Dockerfile"
  args       = { PHP_VERSION = "7.3", VARIANT = "release" }
  tags       = ["datadog/system-tests:apache-mod-7.3.base"]
}

target "apache-mod-7_4" {
  inherits   = ["_common"]
  dockerfile = "apache-mod.base.Dockerfile"
  args       = { PHP_VERSION = "7.4", VARIANT = "release" }
  tags       = ["datadog/system-tests:apache-mod-7.4.base"]
}

target "apache-mod-8_0" {
  inherits   = ["_common"]
  dockerfile = "apache-mod.base.Dockerfile"
  args       = { PHP_VERSION = "8.0", VARIANT = "release" }
  tags       = ["datadog/system-tests:apache-mod-8.0.base"]
}

target "apache-mod-8_1" {
  inherits   = ["_common"]
  dockerfile = "apache-mod.base.Dockerfile"
  args       = { PHP_VERSION = "8.1", VARIANT = "release" }
  tags       = ["datadog/system-tests:apache-mod-8.1.base"]
}

target "apache-mod-8_2" {
  inherits   = ["_common"]
  dockerfile = "apache-mod.base.Dockerfile"
  args       = { PHP_VERSION = "8.2", VARIANT = "release" }
  tags       = ["datadog/system-tests:apache-mod-8.2.base"]
}

target "apache-mod-7_0-zts" {
  inherits   = ["_common"]
  dockerfile = "apache-mod.base.Dockerfile"
  args       = { PHP_VERSION = "7.0", VARIANT = "release-zts" }
  tags       = ["datadog/system-tests:apache-mod-7.0-zts.base"]
}

target "apache-mod-7_1-zts" {
  inherits   = ["_common"]
  dockerfile = "apache-mod.base.Dockerfile"
  args       = { PHP_VERSION = "7.1", VARIANT = "release-zts" }
  tags       = ["datadog/system-tests:apache-mod-7.1-zts.base"]
}

target "apache-mod-7_2-zts" {
  inherits   = ["_common"]
  dockerfile = "apache-mod.base.Dockerfile"
  args       = { PHP_VERSION = "7.2", VARIANT = "release-zts" }
  tags       = ["datadog/system-tests:apache-mod-7.2-zts.base"]
}

target "apache-mod-7_3-zts" {
  inherits   = ["_common"]
  dockerfile = "apache-mod.base.Dockerfile"
  args       = { PHP_VERSION = "7.3", VARIANT = "release-zts" }
  tags       = ["datadog/system-tests:apache-mod-7.3-zts.base"]
}

target "apache-mod-7_4-zts" {
  inherits   = ["_common"]
  dockerfile = "apache-mod.base.Dockerfile"
  args       = { PHP_VERSION = "7.4", VARIANT = "release-zts" }
  tags       = ["datadog/system-tests:apache-mod-7.4-zts.base"]
}

target "apache-mod-8_0-zts" {
  inherits   = ["_common"]
  dockerfile = "apache-mod.base.Dockerfile"
  args       = { PHP_VERSION = "8.0", VARIANT = "release-zts" }
  tags       = ["datadog/system-tests:apache-mod-8.0-zts.base"]
}

target "apache-mod-8_1-zts" {
  inherits   = ["_common"]
  dockerfile = "apache-mod.base.Dockerfile"
  args       = { PHP_VERSION = "8.1", VARIANT = "release-zts" }
  tags       = ["datadog/system-tests:apache-mod-8.1-zts.base"]
}

target "apache-mod-8_2-zts" {
  inherits   = ["_common"]
  dockerfile = "apache-mod.base.Dockerfile"
  args       = { PHP_VERSION = "8.2", VARIANT = "release-zts" }
  tags       = ["datadog/system-tests:apache-mod-8.2-zts.base"]
}

target "php-fpm-7_0" {
  inherits   = ["_common"]
  dockerfile = "php-fpm.base.Dockerfile"
  args       = { PHP_VERSION = "7.0" }
  tags       = ["datadog/system-tests:php-fpm-7.0.base"]
}

target "php-fpm-7_1" {
  inherits   = ["_common"]
  dockerfile = "php-fpm.base.Dockerfile"
  args       = { PHP_VERSION = "7.1" }
  tags       = ["datadog/system-tests:php-fpm-7.1.base"]
}

target "php-fpm-7_2" {
  inherits   = ["_common"]
  dockerfile = "php-fpm.base.Dockerfile"
  args       = { PHP_VERSION = "7.2" }
  tags       = ["datadog/system-tests:php-fpm-7.2.base"]
}

target "php-fpm-7_3" {
  inherits   = ["_common"]
  dockerfile = "php-fpm.base.Dockerfile"
  args       = { PHP_VERSION = "7.3" }
  tags       = ["datadog/system-tests:php-fpm-7.3.base"]
}

target "php-fpm-7_4" {
  inherits   = ["_common"]
  dockerfile = "php-fpm.base.Dockerfile"
  args       = { PHP_VERSION = "7.4" }
  tags       = ["datadog/system-tests:php-fpm-7.4.base"]
}

target "php-fpm-8_0" {
  inherits   = ["_common"]
  dockerfile = "php-fpm.base.Dockerfile"
  args       = { PHP_VERSION = "8.0" }
  tags       = ["datadog/system-tests:php-fpm-8.0.base"]
}

target "php-fpm-8_1" {
  inherits   = ["_common"]
  dockerfile = "php-fpm.base.Dockerfile"
  args       = { PHP_VERSION = "8.1" }
  tags       = ["datadog/system-tests:php-fpm-8.1.base"]
}

target "php-fpm-8_2" {
  inherits   = ["_common"]
  dockerfile = "php-fpm.base.Dockerfile"
  args       = { PHP_VERSION = "8.2" }
  tags       = ["datadog/system-tests:php-fpm-8.2.base"]
}

target "php-fpm-8_5" {
  inherits   = ["_common"]
  dockerfile = "php-fpm.base.Dockerfile"
  args       = { PHP_VERSION = "8.5" }
  tags       = ["datadog/system-tests:php-fpm-8.5.base"]
}
