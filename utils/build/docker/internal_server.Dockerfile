# Multi-arch replacement for the amd64-only demisto/fastapi:0.116.1.4266494, used by
# InternalServerContainer (utils/_context/containers.py) in GitLab CI so it also runs on
# arm64 runners. Built and published by utils/ci/gitlab/build_ci_image.py.
# Alpine provides the busybox wget used by the container healthcheck.
FROM python:3.12-alpine

RUN pip install --no-cache-dir fastapi==0.116.1 uvicorn==0.35.0

WORKDIR /app
