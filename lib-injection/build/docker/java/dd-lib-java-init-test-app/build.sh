#!/bin/bash

./gradlew -PdockerImageRepo=${APP_DOCKER_IMAGE_REPO} -PdockerImageTag=${DOCKER_IMAGE_WEBLOG_TAG} clean bootBuildImage
docker push ${APP_DOCKER_IMAGE_REPO}:${DOCKER_IMAGE_WEBLOG_TAG}
