# Docker Buildx bake file for Java base images

group "default" {
  targets = ["java-jetty-classpath"]
}

target "java-jetty-classpath" {
  context    = "."
  dockerfile = "utils/build/docker/java/jetty-classpath.base.Dockerfile"
  args       = { JETTY_VERSION = "9.4.56.v20240826" }
  tags       = ["datadog/system-tests:java-jetty-9.4.56.v20240826.base-v1"]
}
