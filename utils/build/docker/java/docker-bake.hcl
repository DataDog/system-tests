# Docker Buildx bake file for Java base images
#
# `context` is always this directory: base image Dockerfiles only COPY files from
# here, so paths in the Dockerfile are relative to it (see build_base_images.py,
# which derives base_image_dependencies from these COPY instructions).

group "default" {
  targets = [
    "akka-http",
    "jersey-grizzly2",
    "play",
    "ratpack",
    "resteasy-netty3",
    "spring-boot",
    "spring-boot-3-native",
    "spring-boot-jetty",
    "spring-boot-openliberty",
    "spring-boot-payara",
    "spring-boot-undertow",
    "spring-boot-wildfly",
    "uds-spring-boot",
    "vertx3",
    "vertx4",
  ]
}

target "_common" {
  context = "."
}

target "uds-spring-boot" {
  inherits   = ["_common"]
  dockerfile = "uds-spring-boot.base.Dockerfile"
  tags       = ["datadog/system-tests:uds-spring-boot.base"]
}

target "vertx3" {
  inherits   = ["_common"]
  dockerfile = "vertx3.base.Dockerfile"
  tags       = ["datadog/system-tests:vertx3.base"]
}

target "play" {
  inherits   = ["_common"]
  dockerfile = "play.base.Dockerfile"
  tags       = ["datadog/system-tests:play.base"]
}

target "ratpack" {
  inherits   = ["_common"]
  dockerfile = "ratpack.base.Dockerfile"
  tags       = ["datadog/system-tests:ratpack.base"]
}

target "vertx4" {
  inherits   = ["_common"]
  dockerfile = "vertx4.base.Dockerfile"
  tags       = ["datadog/system-tests:vertx4.base"]
}

target "spring-boot" {
  inherits   = ["_common"]
  dockerfile = "spring-boot.base.Dockerfile"
  args       = { MAVEN_PROFILE = "tomcat" }
  tags       = ["datadog/system-tests:spring-boot.base"]
}

target "spring-boot-jetty" {
  inherits   = ["_common"]
  dockerfile = "spring-boot.base.Dockerfile"
  args       = { MAVEN_PROFILE = "jetty" }
  tags       = ["datadog/system-tests:spring-boot-jetty.base"]
}

target "spring-boot-openliberty" {
  inherits   = ["_common"]
  dockerfile = "spring-boot.base.Dockerfile"
  args       = { MAVEN_PROFILE = "openliberty" }
  tags       = ["datadog/system-tests:spring-boot-openliberty.base"]
}

target "spring-boot-payara" {
  inherits   = ["_common"]
  dockerfile = "spring-boot.base.Dockerfile"
  args       = { MAVEN_PROFILE = "payara" }
  tags       = ["datadog/system-tests:spring-boot-payara.base"]
}

target "spring-boot-undertow" {
  inherits   = ["_common"]
  dockerfile = "spring-boot.base.Dockerfile"
  args       = { MAVEN_PROFILE = "undertow" }
  tags       = ["datadog/system-tests:spring-boot-undertow.base"]
}

target "spring-boot-wildfly" {
  inherits   = ["_common"]
  dockerfile = "spring-boot.base.Dockerfile"
  args       = { MAVEN_PROFILE = "wildfly" }
  tags       = ["datadog/system-tests:spring-boot-wildfly.base"]
}

target "akka-http" {
  inherits   = ["_common"]
  dockerfile = "akka-http.base.Dockerfile"
  tags       = ["datadog/system-tests:akka-http.base"]
}

target "jersey-grizzly2" {
  inherits   = ["_common"]
  dockerfile = "jersey-grizzly2.base.Dockerfile"
  tags       = ["datadog/system-tests:jersey-grizzly2.base"]
}

target "resteasy-netty3" {
  inherits   = ["_common"]
  dockerfile = "resteasy-netty3.base.Dockerfile"
  tags       = ["datadog/system-tests:resteasy-netty3.base"]
}

target "spring-boot-3-native" {
  inherits   = ["_common"]
  dockerfile = "spring-boot-3-native.base.Dockerfile"
  tags       = ["datadog/system-tests:spring-boot-3-native.base"]
}
