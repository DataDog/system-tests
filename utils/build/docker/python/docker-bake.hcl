# Docker Buildx bake file for python base images
#
# `context` is always this directory: base image Dockerfiles only COPY files from
# here, so paths in the Dockerfile are relative to it (see build_base_images.py,
# which derives base_image_dependencies from these COPY instructions).

group "default" {
  targets = [
    "django-py3_13",
    "fastapi",
    "python3_12",
    "django-poc",
    "flask-poc",
    "uwsgi-poc",
    "tornado",
  ]
}

target "_common" {
  context = "."
}

target "django-py3_13" {
  inherits   = ["_common"]
  dockerfile = "django-py3.13.base.Dockerfile"
  tags       = ["datadog/system-tests:django-py3.13.base"]
}

target "fastapi" {
  inherits   = ["_common"]
  dockerfile = "fastapi.base.Dockerfile"
  tags       = ["datadog/system-tests:fastapi.base"]
}

target "python3_12" {
  inherits   = ["_common"]
  dockerfile = "python3.12.base.Dockerfile"
  tags       = ["datadog/system-tests:python3.12.base"]
}

target "django-poc" {
  inherits   = ["_common"]
  dockerfile = "django-poc.base.Dockerfile"
  tags       = ["datadog/system-tests:django-poc.base"]
}

target "flask-poc" {
  inherits   = ["_common"]
  dockerfile = "flask-poc.base.Dockerfile"
  tags       = ["datadog/system-tests:flask-poc.base"]
}

target "uwsgi-poc" {
  inherits   = ["_common"]
  dockerfile = "uwsgi-poc.base.Dockerfile"
  tags       = ["datadog/system-tests:uwsgi-poc.base"]
}

target "tornado" {
  inherits   = ["_common"]
  dockerfile = "tornado.base.Dockerfile"
  tags       = ["datadog/system-tests:tornado.base"]
}
