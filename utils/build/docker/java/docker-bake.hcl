# Docker Buildx bake file for Java base images

group "default" {
  targets = ["java-jetty-classpath"]
}

target "java-jetty-classpath" {
  context    = "."
  dockerfile = "utils/build/docker/java/jetty-classpath.base.Dockerfile"
  args       = { JETTY_VERSION = "9.4.58.v20250814" }
  tags       = ["datadog/system-tests:java-jetty-9.4.58.v20250814.base-v1"]
}
