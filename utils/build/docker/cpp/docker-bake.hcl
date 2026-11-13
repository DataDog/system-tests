# Docker Buildx bake file for C++ base images.

group "default" {
  targets = ["parametric"]
}

target "parametric" {
  context    = "."
  dockerfile = "parametric.base.Dockerfile"
  tags       = ["datadog/system-tests:cpp-parametric.base"]
}
