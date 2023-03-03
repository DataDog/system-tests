#!/bin/bash
export APP_DOCKER_IMAGE_REPO="test" 
export DOCKER_IMAGE_WEBLOG_TAG="test_tests"
cd ../lib-injection/build/docker/java/dd-lib-java-init-test-app/
./gradlew build