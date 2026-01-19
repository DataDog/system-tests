# Docker Buildx bake file for python base images

group "default" {
  targets = [
    "django-py3_13",
    "fastapi",
    "python3_12",
    "django-poc",
    "flask-poc",
    "uwsgi-poc",
  ]
}

target "django-py3_13" {
  context    = "."
  dockerfile = "utils/build/docker/python/django-py3.13.base.Dockerfile"
  tags       = ["datadog/system-tests:django-py3.13.base-v9"]
}

target "fastapi" {
  context    = "."
  dockerfile = "utils/build/docker/python/fastapi.base.Dockerfile"
  tags       = ["datadog/system-tests:fastapi.base-v9"]
}

target "python3_12" {
  context    = "."
  dockerfile = "utils/build/docker/python/python3.12.base.Dockerfile"
  tags       = ["datadog/system-tests:python3.12.base-v12"]
}

target "django-poc" {
  context    = "."
  dockerfile = "utils/build/docker/python/django-poc.base.Dockerfile"
  tags       = ["datadog/system-tests:django-poc.base-v10"]
}

target "flask-poc" {
  context    = "."
  dockerfile = "utils/build/docker/python/flask-poc.base.Dockerfile"
  tags       = ["datadog/system-tests:flask-poc.base-v13"]
}

target "uwsgi-poc" {
  context    = "."
  dockerfile = "utils/build/docker/python/uwsgi-poc.base.Dockerfile"
  tags       = ["datadog/system-tests:uwsgi-poc.base-v9"]
}
